#!/usr/bin/env python3
"""
MediaWiki deploy webhook.

Listens for GitHub push events, runs `git pull` on the content repo, then
syncs changed files to a MediaWiki instance via the Action API.

Can also be run manually to sync all mapped pages:
    python3 webhook.py sync-all

Environment variables (required):
    WIKI_URL          Base URL of the wiki, e.g. https://altered.wiki
    WIKI_USERNAME     Bot username in Special:BotPasswords format (User@BotName)
    WIKI_PASSWORD     Bot password
    WEBHOOK_SECRET    GitHub webhook secret for HMAC-SHA256 verification
    REPO_PATH         Absolute path to the local checkout of the content repo

Environment variables (optional):
    WEBHOOK_PORT      Port to listen on (default: 9000)

Page mapping:
    Defined in pages.json next to this script. Maps repo-relative file paths
    to wiki page names. Edit it to match your repo layout.
"""

import hashlib
import hmac
import http.server
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def require_env(name):
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# ---------------------------------------------------------------------------
# MediaWiki API client
# ---------------------------------------------------------------------------

class MediaWikiClient:
    def __init__(self, base_url, username, password):
        self.api = base_url.rstrip("/") + "/api.php"
        self._cookies = {}
        self._login(username, password)

    def _post(self, **params):
        params["format"] = "json"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(self.api, data=data)
        if self._cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self._cookies.items()))
        with urllib.request.urlopen(req) as resp:
            for header in resp.headers.get_all("Set-Cookie") or []:
                name, _, rest = header.partition("=")
                value = rest.split(";")[0]
                self._cookies[name.strip()] = value.strip()
            return json.loads(resp.read())

    def _login(self, username, password):
        r = self._post(action="query", meta="tokens", type="login")
        token = r["query"]["tokens"]["logintoken"]
        r = self._post(action="login", lgname=username, lgpassword=password, lgtoken=token)
        if r.get("login", {}).get("result") != "Success":
            raise RuntimeError(f"MediaWiki login failed: {r['login']}")

    def _csrf_token(self):
        r = self._post(action="query", meta="tokens")
        return r["query"]["tokens"]["csrftoken"]

    def edit(self, title, content, summary="Automated sync"):
        r = self._post(
            action="edit",
            title=title,
            text=content,
            summary=summary,
            bot="1",
            token=self._csrf_token(),
        )
        edit = r.get("edit", {})
        if edit.get("result") != "Success":
            raise RuntimeError(f"Edit failed for {title!r}: {r}")
        return "no-op" if "nochange" in edit else "updated"


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def git_pull(repo_path):
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    print(result.stdout.strip() or "(git pull: already up to date)")
    if result.returncode != 0:
        raise RuntimeError(f"git pull failed: {result.stderr.strip()}")


def load_page_map(repo_path):
    path = os.path.join(repo_path, "pages.json")
    if not os.path.isfile(path):
        raise RuntimeError(f"pages.json not found in repo root: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sync_files(paths, repo_path):
    page_map = load_page_map(repo_path)
    client = MediaWikiClient(
        require_env("WIKI_URL"),
        require_env("WIKI_USERNAME"),
        require_env("WIKI_PASSWORD"),
    )
    for path in paths:
        page = page_map.get(path)
        if not page:
            print(f"  skip {path} (not in pages.json)")
            continue
        full = os.path.join(repo_path, path)
        if not os.path.isfile(full):
            print(f"  skip {path} (not found in repo)")
            continue
        with open(full, encoding="utf-8") as f:
            content = f.read()
        status = client.edit(page, content)
        print(f"  {path} → {page}: {status}")


# ---------------------------------------------------------------------------
# Webhook server
# ---------------------------------------------------------------------------

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        secret = require_env("WEBHOOK_SECRET").encode()
        sig_header = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            self._respond(403, "Invalid signature")
            return

        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            self._respond(200, f"Ignored: {event}")
            return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, "Bad JSON")
            return

        changed = set()
        for commit in payload.get("commits", []):
            changed.update(commit.get("added", []))
            changed.update(commit.get("modified", []))

        repo_path = require_env("REPO_PATH")
        print(f"Push received — changed: {sorted(changed)}")
        try:
            git_pull(repo_path)
            sync_files(sorted(changed), repo_path)
            self._respond(200, "OK")
        except Exception as exc:
            print(f"ERROR: {exc}")
            self._respond(500, str(exc))

    def _respond(self, code, msg):
        body = msg.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "sync-all":
        repo_path = require_env("REPO_PATH")
        print("Syncing all mapped files…")
        sync_files(list(PAGE_MAP.keys()), repo_path)
        return

    port = int(os.environ.get("WEBHOOK_PORT", 9000))
    print(f"Listening on :{port}")
    http.server.HTTPServer(("", port), WebhookHandler).serve_forever()


if __name__ == "__main__":
    main()
