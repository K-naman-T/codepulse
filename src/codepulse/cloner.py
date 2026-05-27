"""Clone and cache repos from URLs for analysis.

Downloads via GitHub tarball (fast, no git needed), caches by commit hash.
"""

import hashlib
import io
import json
import os
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

import requests

from codepulse.repo_utils import RepoURL, parse_git_url


_CLONE_LOCKS: dict[str, threading.Lock] = {}
_CLONE_LOCK_LOCK = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    """Get or create a per-repo lock to prevent concurrent clones."""
    with _CLONE_LOCK_LOCK:
        if key not in _CLONE_LOCKS:
            _CLONE_LOCKS[key] = threading.Lock()
        return _CLONE_LOCKS[key]


class RepoCache:
    """Cache analyzed repos by commit hash."""
    
    def __init__(self, cache_dir: str = "~/.cache/codepulse/repos"):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, repo_url: RepoURL) -> str:
        raw = f"{repo_url.full_name}:{repo_url.branch}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_head_commit(self, repo_url: RepoURL, token: str | None = None) -> tuple[str, str]:
        """Get latest commit SHA from tarball redirect URL (race-condition-free).

        GitHub returns a 302 redirect to a URL containing the commit SHA:
          /owner/repo/legacy.zip/{ref} → /owner/repo/{sha}.zip

        We follow the redirect with GET, extract the SHA from the URL.

        Returns (sha, actual_branch).
        """
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        tried_branches = [repo_url.branch] if repo_url.branch != "main" else ["main"]
        if "master" not in tried_branches:
            tried_branches.append("master")

        for branch in tried_branches:
            dl_url = f"https://api.github.com/repos/{repo_url.owner}/{repo_url.name}/zipball/{branch}"
            r = requests.get(dl_url, headers=headers, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                sha = self._extract_sha_from_response(r, dl_url)
                if sha:
                    return sha, branch
                api_url = f"https://api.github.com/repos/{repo_url.owner}/{repo_url.name}/git/ref/heads/{branch}"
                ar = requests.get(api_url, headers=headers, timeout=15)
                if ar.status_code == 200:
                    return ar.json()["object"]["sha"], branch
            elif r.status_code == 404:
                continue
        raise ValueError(f"Could not find default branch for {repo_url.full_name}")

    def _extract_sha_from_response(self, response: requests.Response, dl_url: str) -> str | None:
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            import re as _re
            m = _re.search(r"filename=[\"']?[^\"']+-[^\"']+-([a-f0-9]{7,40})", cd)
            if m:
                return m.group(1)
        final_url = response.url
        parts = final_url.rstrip("/").split("/")
        if parts and len(parts[-1]) >= 7 and all(c in "0123456789abcdef" for c in parts[-1]):
            return parts[-1]
        return None

    def is_cached(self, repo_url: RepoURL, commit: str) -> bool:
        key = self._cache_key(repo_url)
        manifest = self.cache_dir / key / "manifest.json"
        if not manifest.exists():
            return False
        with open(manifest) as f:
            data = json.load(f)
        return data.get("commit") == commit

    def get(self, repo_url: RepoURL, commit: str) -> Path | None:
        key = self._cache_key(repo_url)
        path = self.cache_dir / key
        if self.is_cached(repo_url, commit):
            return path / "repo"
        return None

    def store(self, repo_url: RepoURL, commit: str, source: str) -> Path:
        key = self._cache_key(repo_url)
        dest = self.cache_dir / key
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(source, str(dest / "repo"))
        with open(dest / "manifest.json", "w") as f:
            json.dump({
                "url": repo_url.full_name,
                "branch": repo_url.branch,
                "commit": commit,
                "cloned_at": time.time(),
            }, f)
        return dest / "repo"

    def clean(self, max_age_days: int = 7) -> int:
        """Remove old caches. Returns bytes freed."""
        freed = 0
        now = time.time()
        for d in self.cache_dir.iterdir():
            if d.is_dir():
                m = d / "manifest.json"
                if m.exists():
                    age = now - m.stat().st_mtime
                    if age > max_age_days * 86400:
                        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                        shutil.rmtree(d)
                        freed += size
        return freed


def clone_repo(
    url: str,
    token: str | None = None,
    on_progress: Callable[[str], None] | None = None,
    cache: RepoCache | None = None,
    max_size_mb: int = 500,
) -> str:
    """Clone a git repo by URL and return the local path.

    Uses tarball download (no git binary needed), caches by commit hash.
    Thread-safe: concurrent clones of the same repo are serialized.

    Raises ValueError if the repo is too large or URL can't be parsed.
    Returns path to the extracted repo directory.
    """
    parsed = parse_git_url(url)
    if not parsed:
        raise ValueError(f"Could not parse repo URL: {url}")

    if on_progress:
        on_progress(f"Resolving {parsed.full_name}...")

    cache = cache or RepoCache()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    lock_key = f"{parsed.full_name}:{parsed.branch}"
    lock = _get_lock(lock_key)

    with lock:
        commit, actual_branch = cache.get_head_commit(parsed, token)
        parsed.branch = actual_branch

        cached = cache.get(parsed, commit)
        if cached and cached.exists():
            if on_progress:
                on_progress(f"Using cached analysis (commit {commit[:8]})")
            return str(cached)

        if on_progress:
            on_progress(f"Downloading {parsed.full_name}...")

        dl_url = parsed.archive_url
        if not dl_url:
            raise ValueError(f"Unsupported platform for archive download: {parsed.platform}")

        r = requests.get(dl_url, headers=headers, timeout=120, stream=True)
        if r.status_code == 404:
            raise ValueError(f"Repository not found: {parsed.full_name}")
        if r.status_code == 403:
            raise PermissionError(f"Access denied to {parsed.full_name}. Use --token for private repos.")
        r.raise_for_status()

        content_length = r.headers.get("Content-Length")
        if content_length and int(content_length) > max_size_mb * 1024 * 1024:
            raise ValueError(f"Repository too large ({int(content_length)//1024//1024}MB). Max: {max_size_mb}MB")

        tmp = tempfile.mkdtemp(prefix="codepulse-")
        try:
            data = r.content
            z = zipfile.ZipFile(io.BytesIO(data))
            root_dir = z.namelist()[0].split("/")[0]
            z.extractall(tmp)

            repo_path = Path(tmp) / root_dir
            if not repo_path.exists():
                repo_path = Path(tmp)

            if on_progress:
                file_count = len(list(repo_path.rglob("*")))
                on_progress(f"Extracted {file_count} files")

            final_path = cache.store(parsed, commit, str(repo_path))
            if on_progress:
                on_progress(f"Cached at {final_path}")

            return str(final_path)

        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise



