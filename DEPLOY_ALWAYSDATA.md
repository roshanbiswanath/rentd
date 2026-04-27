# Deploying This Scraper on alwaysdata

This project can run on alwaysdata as a scheduled background job (recommended).

## 1) Create and prepare your alwaysdata account

- Enable SSH access in the alwaysdata admin panel.
- In Environment > Node.js, set a supported Node.js version (recommended: 20 or 22).

Official docs:
- Node.js: https://help.alwaysdata.com/en/web-hosting/languages/nodejs/
- Node.js configuration: https://help.alwaysdata.com/en/web-hosting/languages/nodejs/configuration/
- Scheduled tasks: https://help.alwaysdata.com/en/web-hosting/tasks/
- Services: https://help.alwaysdata.com/en/web-hosting/services/

## 2) Upload project files via SSH

```bash
ssh <user>@ssh-<account>.alwaysdata.net
cd ~
git clone <your-repo-url> homie
cd homie
npm ci
```

Install Chromium for Playwright in your user space:

```bash
npx playwright install chromium
```

## 3) Prepare Facebook session state locally and upload

Because alwaysdata jobs/services are headless, prepare login state locally first:

```bash
npm ci
npx playwright install chromium
npm run prepare-session
```

This creates `.facebook-state.json` locally after you log in.

Upload it to alwaysdata (from your local machine):

```bash
scp .facebook-state.json <user>@ssh-<account>.alwaysdata.net:/home/<account>/.facebook-state.json
```

On the server:

```bash
ssh <user>@ssh-<account>.alwaysdata.net
chmod 600 ~/.facebook-state.json
```

## 4) Make the helper script executable

```bash
cd ~/homie
chmod +x scripts/alwaysdata-scrape.sh
```

## 5) Run one manual test on server

```bash
cd ~/homie
GROUP_URL="https://www.facebook.com/groups/<group-id>/" sh scripts/alwaysdata-scrape.sh
```

Optional MongoDB env vars:

```bash
MONGO_URI="mongodb://..."
MONGO_DB="facebook_scraper"
MONGO_COLLECTION="group_posts"
```

Then run with Mongo:

```bash
cd ~/homie
GROUP_URL="https://www.facebook.com/groups/<group-id>/" \
MONGO_URI="$MONGO_URI" MONGO_DB="$MONGO_DB" MONGO_COLLECTION="$MONGO_COLLECTION" \
sh scripts/alwaysdata-scrape.sh
```

## 6) Create a scheduled task in alwaysdata

In alwaysdata admin:
- Go to Advanced > Scheduled tasks.
- Task type: Command.
- Frequency: choose your interval (for example every 10 minutes).
- Command:

```bash
cd $HOME/homie && GROUP_URL="https://www.facebook.com/groups/<group-id>/" sh scripts/alwaysdata-scrape.sh
```

Useful notes from alwaysdata docs:
- Job logs are in `$HOME/admin/logs/jobs/`.
- If a previous run is still in progress, the next run is skipped.
- Default language versions come from Environment settings.

## 7) Optional: run as always-on service instead of scheduled task

Use this only if you truly need a continuously running worker.

Service command example:

```bash
cd $HOME/homie && GROUP_URL="https://www.facebook.com/groups/<group-id>/" /usr/bin/node facebook-group-scraper.mjs --headless --continuous --poll-interval-seconds 300 --state-file "$HOME/.facebook-state.json" --output "$HOME/group_posts.json"
```

Service notes:
- Services must run in foreground.
- Service logs are in `$HOME/admin/logs/services/`.
- Services can be restarted automatically by alwaysdata.

## Troubleshooting

1. Browser launch fails on server:
   - Re-run `npx playwright install chromium` on alwaysdata SSH.
   - Ensure `PLAYWRIGHT_BROWSERS_PATH` points to a writable directory (the helper script defaults to `$HOME/.cache/ms-playwright`).

2. Authentication/session errors:
   - Recreate `.facebook-state.json` locally with `npm run prepare-session` and upload again.
   - Make sure the account still has access to the target group.

3. No output file updates:
   - Check job logs in `$HOME/admin/logs/jobs/`.
   - Verify `GROUP_URL` is set in the scheduled task command.

4. MongoDB not writing:
   - Verify `MONGO_URI` is reachable from alwaysdata.
   - Confirm Mongo credentials and network rules.
