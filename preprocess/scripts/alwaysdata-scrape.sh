#!/bin/sh
set -eu

# Usage:
#   GROUP_URL="https://www.facebook.com/groups/<id>/" sh scripts/alwaysdata-scrape.sh
#
# Optional env vars:
#   PROJECT_DIR, STATE_FILE, OUTPUT_FILE, MAX_POSTS, SCROLL_DELAY_MS,
#   MAX_EMPTY_SCROLLS, MONGO_URI, MONGO_DB, MONGO_COLLECTION, NODEJS_VERSION,
#   PLAYWRIGHT_BROWSERS_PATH

PROJECT_DIR="${PROJECT_DIR:-$HOME/homie}"
GROUP_URL="${GROUP_URL:-}"
STATE_FILE="${STATE_FILE:-$HOME/.facebook-state.json}"
OUTPUT_FILE="${OUTPUT_FILE:-$HOME/group_posts.json}"
MAX_POSTS="${MAX_POSTS:-100}"
SCROLL_DELAY_MS="${SCROLL_DELAY_MS:-1800}"
MAX_EMPTY_SCROLLS="${MAX_EMPTY_SCROLLS:-8}"
NODEJS_VERSION="${NODEJS_VERSION:-20}"
PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"

if [ -z "$GROUP_URL" ]; then
  echo "GROUP_URL is required."
  echo "Example: GROUP_URL=\"https://www.facebook.com/groups/123456789/\" sh scripts/alwaysdata-scrape.sh"
  exit 2
fi

if [ ! -f "$STATE_FILE" ]; then
  echo "State file not found: $STATE_FILE"
  echo "Create it locally with 'npm run prepare-session' and upload it to the server."
  exit 3
fi

export NODEJS_VERSION
export PLAYWRIGHT_BROWSERS_PATH

cd "$PROJECT_DIR"

set -- /usr/bin/node facebook-group-scraper.mjs \
  --group-url "$GROUP_URL" \
  --max-posts "$MAX_POSTS" \
  --output "$OUTPUT_FILE" \
  --state-file "$STATE_FILE" \
  --scroll-delay-ms "$SCROLL_DELAY_MS" \
  --max-empty-scrolls "$MAX_EMPTY_SCROLLS" \
  --headless

if [ -n "${MONGO_URI:-}" ]; then
  set -- "$@" --mongo-uri "$MONGO_URI"
fi

if [ -n "${MONGO_DB:-}" ]; then
  set -- "$@" --mongo-db "$MONGO_DB"
fi

if [ -n "${MONGO_COLLECTION:-}" ]; then
  set -- "$@" --mongo-collection "$MONGO_COLLECTION"
fi

exec "$@"
