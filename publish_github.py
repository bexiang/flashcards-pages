#!/usr/bin/env python3
"""
Publish HTML files/folders to GitHub Pages via the Contents API (no git needed).

One-time setup (creates GitHub repo + enables Pages):

    python3 publish_github.py --init

Publish an HTML file (permanent):

    python3 publish_github.py --html-file flashcards_20260318.html

Publish a whole folder (must contain index.html):

    python3 publish_github.py --upload-folder publish --project-name "my-site"

Token sources (checked in this order):
  - --token
  - --token-file
  - env: GITHUB_TOKEN
  - file: ./.github_token
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TOKEN_FILE = ".github_token"
DEFAULT_REPO_NAME = "bexiang.github.io"
GITHUB_API = "https://api.github.com"


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _get_token(args_token=None, args_token_file=None) -> str:
    if args_token:
        return args_token.strip()
    if args_token_file:
        token = _read_text_file(args_token_file).strip()
        if not token:
            raise SystemExit(f"Token file is empty: {args_token_file}")
        return token
    env = os.environ.get("GITHUB_TOKEN", "").strip()
    if env:
        return env
    if os.path.exists(DEFAULT_TOKEN_FILE):
        token = _read_text_file(DEFAULT_TOKEN_FILE).strip()
        if not token:
            raise SystemExit(f"Token file is empty: {DEFAULT_TOKEN_FILE}")
        return token
    return ""


def _github_api(method: str, path: str, token: str, body: dict = None) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    url = f"{GITHUB_API}{path}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(detail)
            msg = err.get("message", detail)
            if "errors" in err:
                for er in err["errors"]:
                    msg += f"\n  {er.get('message', er)}"
        except json.JSONDecodeError:
            msg = detail
        raise SystemExit(f"GitHub API {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Network error: {e}")

    if not raw.strip():
        return {}
    return json.loads(raw)


def _get_username(token: str) -> str:
    user = _github_api("GET", "/user", token)
    login = user.get("login")
    if not login:
        raise SystemExit("Could not determine GitHub username from API response.")
    return login


def _ensure_repo(token: str, username: str, repo_name: str) -> dict:
    """Ensure the GitHub repo exists. Returns repo info dict."""
    try:
        return _github_api("GET", f"/repos/{username}/{repo_name}", token)
    except SystemExit:
        pass
    return _github_api("POST", "/user/repos", token, {
        "name": repo_name,
        "auto_init": True,
        "public": True,
        "description": "Flashcards published via GitHub Pages",
    })


def _enable_pages(token: str, username: str, repo_name: str) -> None:
    """Enable GitHub Pages. Ignores error if already enabled."""
    try:
        _github_api("POST", f"/repos/{username}/{repo_name}/pages", token, {
            "build_type": "legacy",
            "source": {"branch": "main", "path": "/"},
        })
    except SystemExit:
        pass


def _encode_path(path: str) -> str:
    """URL-encode a repo path, keeping / and ASCII chars intact."""
    return urllib.parse.quote(path, safe="/@")


def _get_file_sha(token: str, username: str, repo_name: str, path: str) -> str:
    """Get the SHA of an existing file (needed to update it). Returns '' if not found."""
    try:
        info = _github_api("GET", f"/repos/{username}/{repo_name}/contents/{_encode_path(path)}", token)
        return info.get("sha", "")
    except SystemExit:
        return ""


def _upload_file(token: str, username: str, repo_name: str, repo_path: str,
                 local_path: str, message: str) -> dict:
    """Upload (create or update) a single file via the Contents API."""
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")

    body = {
        "message": message,
        "content": content,
        "branch": "main",
    }
    existing_sha = _get_file_sha(token, username, repo_name, repo_path)
    if existing_sha:
        body["sha"] = existing_sha

    return _github_api("PUT", f"/repos/{username}/{repo_name}/contents/{_encode_path(repo_path)}", token, body)


def _iter_files(root_dir: str):
    """Yield (relative_path, absolute_path) for all files under root_dir."""
    root_dir = os.path.abspath(root_dir)
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_dir).replace(os.sep, "/")
            yield rel, full


def cmd_init(token: str, repo_name: str) -> int:
    username = _get_username(token)
    print(f"GitHub user: {username}")
    _ensure_repo(token, username, repo_name)
    _enable_pages(token, username, repo_name)
    url = f"https://{username}.github.io/{repo_name}/"
    print(f"Initialized: {url}")
    print("Note: GitHub Pages may take 1-2 minutes to go live.")
    return 0


def _pages_base_url(username: str, repo_name: str) -> str:
    """Return the base URL for GitHub Pages (no trailing slash)."""
    if repo_name == f"{username}.github.io":
        return f"https://{username}.github.io"
    return f"https://{username}.github.io/{repo_name}"


def cmd_publish_file(token: str, html_file: str, repo_name: str,
                     project_name: str = None, repo_subdir: str = None) -> int:
    username = _get_username(token)
    _ensure_repo(token, username, repo_name)

    basename = os.path.basename(html_file)

    # If project_name given, put file in a subdirectory as index.html
    if project_name:
        repo_path = f"{project_name}/index.html"
    elif repo_subdir:
        repo_path = f"{repo_subdir}/{basename}"
    else:
        repo_path = basename

    name = os.path.splitext(basename)[0]
    print(f"Uploading {repo_path} ...")
    _upload_file(token, username, repo_name, repo_path, html_file, f"Publish {name}")

    base = _pages_base_url(username, repo_name)
    url = f"{base}/{_encode_path(repo_path)}"
    print(url)
    return 0


def cmd_publish_folder(token: str, folder_dir: str, repo_name: str,
                       project_name: str = None) -> int:
    username = _get_username(token)
    _ensure_repo(token, username, repo_name)

    name = project_name or os.path.basename(os.path.abspath(folder_dir.rstrip("/")))
    files = list(_iter_files(folder_dir))
    if not files:
        raise SystemExit("Folder is empty (no files found).")

    total = len(files)
    for i, (rel, full) in enumerate(files, 1):
        repo_path = f"{name}/{rel}"
        print(f"Uploading [{i}/{total}] {repo_path} ...")
        _upload_file(token, username, repo_name, repo_path, full, f"Publish {name}: {rel}")

    base = _pages_base_url(username, repo_name)
    url = f"{base}/{_encode_path(name)}/"
    print(url)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Publish HTML files/folders to GitHub Pages.",
    )
    ap.add_argument("--init", action="store_true",
                    help="One-time setup: create GitHub repo and enable Pages.")
    ap.add_argument("--html-file", help="Path to HTML file to publish.")
    ap.add_argument("--upload-folder",
                    help="Path to folder to publish (must contain index.html).")
    ap.add_argument("--project-name",
                    help="Name for the project/folder. Default: derived from input.")
    ap.add_argument("--repo-subdir",
                    help="Upload file into this subdirectory in the repo.")
    ap.add_argument("--repo-name", default=DEFAULT_REPO_NAME,
                    help=f"GitHub repo name (default: {DEFAULT_REPO_NAME}).")
    ap.add_argument("--token", help="GitHub Personal Access Token.")
    ap.add_argument("--token-file",
                    help=f"Read token from file (default: ./{DEFAULT_TOKEN_FILE}).")
    args = ap.parse_args()

    if not args.init and not args.html_file and not args.upload_folder:
        ap.print_help()
        return 1

    token = _get_token(args.token, args.token_file)
    if not token:
        raise SystemExit(
            "Missing GitHub token. Create a Personal Access Token at "
            "https://github.com/settings/tokens (needs repo + Pages scope), then:\n"
            f"  echo YOUR_TOKEN > ./{DEFAULT_TOKEN_FILE}"
        )

    if args.init:
        return cmd_init(token, args.repo_name)

    if args.html_file:
        return cmd_publish_file(token, args.html_file, args.repo_name, args.project_name, args.repo_subdir)

    if args.upload_folder:
        return cmd_publish_folder(token, args.upload_folder, args.repo_name, args.project_name)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
