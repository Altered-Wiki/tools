# deploy

Webhook server that syncs wiki content files to a MediaWiki instance
automatically on every push to the content repository.

## How it works

1. GitHub sends a push event to this server.
2. The server verifies the HMAC-SHA256 signature.
3. It runs `git pull` on the local content repo checkout.
4. Changed files listed in `pages.json` are uploaded to the wiki via the Action API.

## Setup

### 1. Create a bot account on your wiki

Go to **Special:BotPasswords** on your wiki and create a bot with the
**Edit pages** permission. Note the `User@BotName` username and generated password.

### 2. Configure environment variables

```sh
export WIKI_URL=https://your.wiki
export WIKI_USERNAME=User@BotName
export WIKI_PASSWORD=the-generated-password
export WEBHOOK_SECRET=a-random-secret-you-choose
export REPO_PATH=/path/to/your/content-repo-checkout
export WEBHOOK_PORT=9000   # optional, default 9000
```

### 3. Add pages.json to your wiki repo

Place a `pages.json` at the root of the repo pointed to by `REPO_PATH`.
It maps repo-relative file paths to wiki page names:

```json
{
    "module-legal-status.lua": "Module:LegalStatus",
    "common-css.css":          "MediaWiki:Common.css"
}
```

### 4. Install and start the systemd service

```sh
# Copy the env file and fill in your values
sudo mkdir -p /etc/altered-wiki
sudo cp deploy.env.example /etc/altered-wiki/deploy.env
sudo $EDITOR /etc/altered-wiki/deploy.env

# Install the service
sudo cp altered-wiki-deploy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now altered-wiki-deploy
```

The service file assumes the tools repo is at `/opt/altered-wiki/tools/`.
Adjust `WorkingDirectory` and `ExecStart` in the unit file if your layout differs.

Run it behind a reverse proxy (nginx/caddy) with TLS for the public webhook endpoint.

### 5. Add the webhook on GitHub

In your content repo → **Settings → Webhooks → Add webhook**:

- **Payload URL:** `https://your.server/` (port 9000 or via reverse proxy)
- **Content type:** `application/json`
- **Secret:** the value of `WEBHOOK_SECRET`
- **Events:** Just the push event

## Manual sync

To push all mapped pages without waiting for a push event:

```sh
python3 webhook.py sync-all
```
