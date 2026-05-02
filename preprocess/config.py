"""
Shared configuration for Rentd scraper and parser.
Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)


# ── MongoDB ──────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "facebook_scraper")
RAW_POSTS_COLLECTION = os.getenv("RAW_POSTS_COLLECTION", "raw_posts")
LISTINGS_COLLECTION = os.getenv("LISTINGS_COLLECTION", "listings")

# ── Gemini API ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

# ── Scraper defaults ────────────────────────────────────────────────────
DEFAULT_MAX_POSTS = int(os.getenv("DEFAULT_MAX_POSTS", "50"))
DEFAULT_SCROLL_DELAY_MS = int(os.getenv("DEFAULT_SCROLL_DELAY_MS", "1800"))
DEFAULT_MAX_EMPTY_SCROLLS = int(os.getenv("DEFAULT_MAX_EMPTY_SCROLLS", "8"))
DEFAULT_POLL_INTERVAL = int(os.getenv("DEFAULT_POLL_INTERVAL", "150"))
DEFAULT_KNOWN_STOP_STREAK = int(os.getenv("DEFAULT_KNOWN_STOP_STREAK", "10"))
DEFAULT_KNOWN_KEYS_LIMIT = int(os.getenv("DEFAULT_KNOWN_KEYS_LIMIT", "10000"))
DEFAULT_DEEP_CAP_MULTIPLIER = int(os.getenv("DEFAULT_DEEP_CAP_MULTIPLIER", "40"))
DEFAULT_PROGRESS_FLUSH_POSTS = int(os.getenv("DEFAULT_PROGRESS_FLUSH_POSTS", str(DEFAULT_MAX_POSTS)))
STATE_FILE = os.getenv("STATE_FILE", ".facebook-state.json")

# ── Parser defaults ─────────────────────────────────────────────────────
PARSER_BATCH_SIZE = int(os.getenv("PARSER_BATCH_SIZE", "10"))
PARSER_POLL_INTERVAL = int(os.getenv("PARSER_POLL_INTERVAL", "120"))
