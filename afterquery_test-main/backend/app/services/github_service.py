from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

import httpx


GITHUB_API = "https://api.github.com"


@dataclass
class GitCloneResult:
    repo_full_name: str
    pinned_main_sha: str


class GitHubService:
    def __init__(self, token: Optional[str] = None, target_owner: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.target_owner = target_owner or os.getenv("GITHUB_TARGET_OWNER")

    def _client(self) -> httpx.Client:
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is not configured")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }
        return httpx.Client(base_url=GITHUB_API, headers=headers, timeout=20.0)

    @staticmethod
    def parse_repo_full_name(repo_url: str) -> str:
        # Accept forms like https://github.com/owner/repo or git@github.com:owner/repo.git
        m_https = re.match(r"https?://github.com/([^/]+)/([^/.]+)(?:\.git)?/?$", repo_url.strip())
        if m_https:
            return f"{m_https.group(1)}/{m_https.group(2)}"
        m_ssh = re.match(r"git@github.com:([^/]+)/([^/.]+)(?:\.git)?$", repo_url.strip())
        if m_ssh:
            return f"{m_ssh.group(1)}/{m_ssh.group(2)}"
        # Already an owner/repo
        if re.match(r"^[^/]+/[^/]+$", repo_url.strip()):
            return repo_url.strip()
        raise ValueError("Unsupported GitHub repo URL format")

    def get_branch_sha(self, full_name: str, branch: str = "main") -> str:
        owner, repo = full_name.split("/")
        with self._client() as c:
            r = c.get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
            r.raise_for_status()
            data = r.json()
            return data["object"]["sha"]

    def ensure_seed_repo(self, source_repo_url: str) -> str:
        # For now, we just parse and return the full name; callers may fetch SHAs via get_branch_sha
        return self.parse_repo_full_name(source_repo_url)

    def create_candidate_repo_from_seed(self, seed_full_name: str, name_hint: Optional[str] = None) -> GitCloneResult:
        if not self.target_owner:
            raise RuntimeError("GITHUB_TARGET_OWNER is not configured")
        owner = self.target_owner
        # Repo naming convention
        suffix = str(int(time.time()))
        repo_name = name_hint or f"candidate-{suffix}"
        pinned_sha = self.get_branch_sha(seed_full_name, branch="main")

        seed_owner, seed_repo = seed_full_name.split("/")
        # Use token-authenticated URL for cloning
        seed_https_url = f"https://{self.token}@github.com/{seed_owner}/{seed_repo}.git"

        with self._client() as c:
            # 1) Create a private repo WITHOUT auto init
            r = c.post(
                f"/orgs/{owner}/repos",
                json={
                    "name": repo_name,
                    "private": True,
                    "auto_init": False,
                    "has_issues": False,
                    "has_projects": False,
                    "has_wiki": False,
                    "description": f"Candidate repo from seed {seed_full_name} (pinned {pinned_sha[:7]})",
                },
            )
            if r.status_code == 404:
                # Fallback to user endpoint if target owner is a user, not org
                r = c.post(
                    "/user/repos",
                    json={
                        "name": repo_name,
                        "private": True,
                        "auto_init": False,
                        "has_issues": False,
                        "has_projects": False,
                        "has_wiki": False,
                        "description": f"Candidate repo from seed {seed_full_name} (pinned {pinned_sha[:7]})",
                    },
                )
            r.raise_for_status()
            repo = r.json()
            full_name = repo["full_name"]
            new_owner, new_repo = full_name.split("/")

            # 2) Clone seed repo to temp directory at the pinned commit
            # Then push to the new candidate repo
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    # Clone the seed repo (full history to ensure we have the pinned commit)
                    subprocess.run(
                        ["git", "clone", seed_https_url, tmpdir],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                    # Checkout the specific pinned commit
                    subprocess.run(
                        ["git", "-C", tmpdir, "checkout", pinned_sha],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                    # Add the candidate repo as a remote and push
                    candidate_repo_url = f"https://{self.token}@github.com/{new_owner}/{new_repo}.git"
                    subprocess.run(
                        ["git", "-C", tmpdir, "remote", "add", "candidate", candidate_repo_url],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                    # Push main branch to the candidate repo
                    subprocess.run(
                        ["git", "-C", tmpdir, "push", "-u", "candidate", "HEAD:refs/heads/main"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Git operation failed: {e.stderr}")

            # 3) Set default branch to main
            c.patch(
                f"/repos/{new_owner}/{new_repo}",
                json={"default_branch": "main"},
            ).raise_for_status()

        return GitCloneResult(repo_full_name=full_name, pinned_main_sha=pinned_sha)

    def create_repo_scoped_token(self, repo_full_name: str, expires_at_iso: str) -> str:
        # Placeholder: Creating fine-grained tokens programmatically isn't supported.
        # Use the app's token for server-side gateway operations, not distribute to clients.
        raise NotImplementedError("Programmatic fine-grained token creation is not supported by GitHub API")

    def compare_commits(self, repo_full_name: str, base: str, head: str = "main") -> dict:
        """
        Compare base...head within the same repository and return GitHub's compare response
        including files with additions/deletions/patch where available.
        """
        owner, repo = repo_full_name.split("/")
        with self._client() as c:
            r = c.get(f"/repos/{owner}/{repo}/compare/{base}...{head}")
            r.raise_for_status()
            return r.json()

    def get_commit_history(self, repo_full_name: str, from_commit: str | None = None) -> list[dict]:
        """
        List commits on 'main' branch, optionally from a specific SHA (exclusive).
        Returns [{sha, author_name, author_email, date, message}]
        """
        owner, repo = repo_full_name.split("/")
        url = f"/repos/{owner}/{repo}/commits"
        params = {"sha": "main", "per_page": 50}
        # If from_commit is provided, API returns prior to this commit,
        # but for now just get latest N since it's tricky to page since/sha in GitHub API v3.
        with self._client() as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            result = []
            for commit in r.json():
                result.append({
                    "sha": commit["sha"],
                    "author_name": commit["commit"]["author"]["name"],
                    "author_email": commit["commit"]["author"]["email"],
                    "date": commit["commit"]["author"]["date"],
                    "message": commit["commit"]["message"],
                    # HTML url etc also available if needed
                })
            return result


    def set_repo_visibility(self, repo_full_name: str, private: bool) -> None:
        """
        Update repository visibility. When private=True, repo becomes private.
        """
        owner, repo = repo_full_name.split("/")
        with self._client() as c:
            r = c.patch(
                f"/repos/{owner}/{repo}",
                json={"private": private},
            )
            r.raise_for_status()

