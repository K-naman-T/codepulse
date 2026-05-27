"""Tests for git URL parsing."""

from codepulse.repo_utils import parse_git_url


class TestParseGitURL:
    def test_github_https(self):
        r = parse_git_url("https://github.com/owner/repo")
        assert r is not None
        assert r.platform == "github"
        assert r.owner == "owner"
        assert r.name == "repo"
        assert r.branch == "main"

    def test_github_https_dot_git(self):
        r = parse_git_url("https://github.com/owner/repo.git")
        assert r is not None
        assert r.owner == "owner"
        assert r.name == "repo"

    def test_github_https_with_branch(self):
        r = parse_git_url("https://github.com/owner/repo/tree/develop")
        assert r is not None
        assert r.owner == "owner"
        assert r.name == "repo"
        assert r.branch == "develop"

    def test_github_https_with_branch_and_path(self):
        r = parse_git_url("https://github.com/owner/repo/tree/main/src/lib")
        assert r is not None
        assert r.owner == "owner"
        assert r.name == "repo"
        assert r.branch == "main"
        assert r.subpath == "src/lib"

    def test_github_ssh(self):
        r = parse_git_url("git@github.com:owner/repo.git")
        assert r is not None
        assert r.platform == "github"
        assert r.owner == "owner"
        assert r.name == "repo"

    def test_gitlab_https(self):
        r = parse_git_url("https://gitlab.com/owner/repo")
        assert r is not None
        assert r.platform == "gitlab"
        assert r.owner == "owner"
        assert r.name == "repo"

    def test_gitlab_with_branch(self):
        r = parse_git_url("https://gitlab.com/owner/repo/-/tree/main/src")
        assert r is not None
        assert r.platform == "gitlab"
        assert r.subpath == "src"

    def test_bitbucket_https(self):
        r = parse_git_url("https://bitbucket.org/owner/repo")
        assert r is not None
        assert r.platform == "bitbucket"
        assert r.owner == "owner"

    def test_archive_url_github(self):
        r = parse_git_url("https://github.com/owner/repo")
        assert r is not None
        assert "api.github.com" in r.archive_url
        assert "/owner/repo/zipball/main" in r.archive_url

    def test_archive_url_empty_for_gitlab(self):
        r = parse_git_url("https://gitlab.com/owner/repo")
        assert r is not None
        assert r.archive_url == ""  # unsupported platform for archive downloads

    def test_full_name(self):
        r = parse_git_url("https://github.com/rails/rails")
        assert r is not None
        assert r.full_name == "rails/rails"

    def test_invalid_url(self):
        assert parse_git_url("") is None
        assert parse_git_url("not a url") is None
        assert parse_git_url("https://example.com/foo/bar") is None
