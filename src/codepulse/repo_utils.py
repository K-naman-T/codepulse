"""Parse git repository URLs into structured components.

Supports GitHub, GitLab, Bitbucket — HTTPS and SSH formats.
"""

import re
from dataclasses import dataclass


@dataclass
class RepoURL:
    platform: str
    owner: str
    name: str
    branch: str = "main"
    subpath: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def archive_url(self) -> str:
        if self.platform == "github":
            return f"https://api.github.com/repos/{self.owner}/{self.name}/zipball/{self.branch}"
        return ""


def parse_git_url(url: str) -> RepoURL | None:
    if not url:
        return None
    url = url.strip().rstrip("/")

    patterns = [
        r"https?://(?:www\.)?github\.com/([^/]+)/([^/.]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?$",
        r"git@github\.com:([^/]+)/([^/.]+?)(?:\.git)?(?:/(?:tree|blob)/([^/]+)(?:/(.*))?)?$",
        r"https?://(?:www\.)?gitlab\.com/([^/]+)/([^/.]+?)(?:\.git)?(?:/-/tree/([^/]+)(?:/(.*))?)?$",
        r"https?://(?:www\.)?bitbucket\.org/([^/]+)/([^/.]+?)(?:\.git)?(?:/src/([^/]+)(?:/(.*))?)?$",
    ]

    for i, pattern in enumerate(patterns):
        m = re.match(pattern, url)
        if m:
            groups = m.groups()
            owner = groups[0]
            name = groups[1]
            branch = groups[2] or "main"
            subpath = groups[3] if len(groups) > 3 else None
            plat = "github"
            if "gitlab" in url:
                plat = "gitlab"
            elif "bitbucket" in url:
                plat = "bitbucket"
            return RepoURL(plat, owner, name, branch, subpath)

    return None
    url = url.strip().rstrip("/")

    patterns = [
        r"https?://(?:www\.)?github\.com/([^/]+)/([^/.]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?$",
        r"git@github\.com:([^/]+)/([^/.]+?)(?:\.git)?(?:/(?:tree|blob)/([^/]+)(?:/(.*))?)?$",
        r"https?://(?:www\.)?gitlab\.com/([^/]+)/([^/.]+?)(?:\.git)?(?:/-/tree/([^/]+)(?:/(.*))?)?$",
        r"https?://(?:www\.)?bitbucket\.org/([^/]+)/([^/.]+?)(?:\.git)?(?:/src/([^/]+)(?:/(.*))?)?$",
    ]

    platform_map = {
        "github.com": "github",
        "gitlab.com": "gitlab",
        "bitbucket.org": "bitbucket",
    }

    for i, pattern in enumerate(patterns):
        m = re.match(pattern, url)
        if m:
            groups = m.groups()
            owner = groups[0]
            name = groups[1]
            branch = groups[2] or "main"
            subpath = groups[3] if len(groups) > 3 else None

            if "github" in url:
                plat = "github"
            elif "gitlab" in url:
                plat = "gitlab"
            elif "bitbucket" in url:
                plat = "bitbucket"
            else:
                plat = "github"

            return RepoURL(plat, owner, name, branch, subpath)

    return None
