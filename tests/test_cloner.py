"""Tests for repo cloner and cache."""

import json
import os
from pathlib import Path

from codepulse.cloner import RepoCache
from codepulse.repo_utils import RepoURL


class TestRepoCache:
    def test_cache_key_is_deterministic(self):
        url = RepoURL("github", "owner", "repo", "main")
        cache = RepoCache("/tmp/test-cache")
        k1 = cache._cache_key(url)
        k2 = cache._cache_key(url)
        assert k1 == k2

    def test_cache_key_differs_for_diff_branches(self):
        cache = RepoCache("/tmp/test-cache")
        main = cache._cache_key(RepoURL("github", "owner", "repo", "main"))
        dev = cache._cache_key(RepoURL("github", "owner", "repo", "develop"))
        assert main != dev

    def test_cache_key_differs_for_diff_owners(self):
        cache = RepoCache("/tmp/test-cache")
        a = cache._cache_key(RepoURL("github", "alice", "repo", "main"))
        b = cache._cache_key(RepoURL("github", "bob", "repo", "main"))
        assert a != b

    def test_is_not_cached_when_empty(self, tmp_path: Path):
        cache = RepoCache(str(tmp_path / "cache"))
        url = RepoURL("github", "o", "r", "main")
        assert not cache.is_cached(url, "abc123")

    def test_store_and_get(self, tmp_path: Path):
        cache = RepoCache(str(tmp_path / "cache"))
        url = RepoURL("github", "o", "r", "main")

        src = tmp_path / "source"
        src.mkdir()
        (src / "test.py").write_text("x = 1")

        stored = cache.store(url, "abc123", str(src))
        assert stored.exists()
        assert (stored / "test.py").read_text() == "x = 1"
        assert cache.is_cached(url, "abc123")
        assert not cache.is_cached(url, "different_commit")

        got = cache.get(url, "abc123")
        assert got is not None
        assert got.exists()

    def test_get_returns_none_for_missing(self, tmp_path: Path):
        cache = RepoCache(str(tmp_path / "cache"))
        url = RepoURL("github", "o", "r", "main")
        assert cache.get(url, "nonexistent") is None

    def test_clean_removes_old_caches(self, tmp_path: Path):
        import time as _time
        cache = RepoCache(str(tmp_path / "cache"))
        url = RepoURL("github", "o", "r", "main")

        src = tmp_path / "source"
        src.mkdir()
        (src / "test.py").write_text("x = 1")
        cache.store(url, "abc", str(src))

        # Manually age the manifest
        import json
        key = cache._cache_key(url)
        manifest = Path(str(tmp_path / "cache")) / key / "manifest.json"
        old_time = _time.time() - 8 * 86400 - 1  # 8 days ago
        # Set both the file content and the mtime
        with open(manifest) as f:
            data = json.load(f)
        data["cloned_at"] = old_time
        with open(manifest, "w") as f:
            json.dump(data, f)
        os.utime(manifest, (old_time, old_time))

        freed = cache.clean(max_age_days=7)
        assert freed > 0, f"Expected freed > 0, cache dir: {manifest.parent}"
        assert not cache.is_cached(url, "abc")
