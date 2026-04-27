# Rentd – Rental Housing Discovery Platform

Rentd aggregates rental housing listings from Facebook groups and transforms them into clean, structured, searchable property listings using LLM-powered parsing.

## Architecture

```
Facebook Group → [scraper.py] → MongoDB:raw_posts → [parser.py + Ollama] → MongoDB:listings
```

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) installed locally with a model (e.g., `ollama pull llama3`)
- A Facebook account that has joined the target group

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Copy `.env.example` → `.env` and fill in your MongoDB URI.

## Usage

### 1. Prepare login session (one-time, headed)

```bash
python scraper.py --prepare-session
```

### 2. Run the scraper

```bash
# Single run
python scraper.py --group-url "https://www.facebook.com/groups/320292845738195/" --headless

# Continuous mode (scrape every 5 minutes)
python scraper.py --group-url "https://www.facebook.com/groups/320292845738195/" --continuous --poll-interval-seconds 300 --headless
```

### 3. Run the LLM parser

```bash
# Continuous mode (watches for new posts)
python parser.py

# Process one batch and exit
python parser.py --once
```

### CLI Options

**scraper.py:**
| Flag | Default | Description |
|------|---------|-------------|
| `--group-url` | required | Facebook group URL |
| `--max-posts` | 50 | Posts per cycle |
| `--headless` | false | Run headless |
| `--continuous` | false | Run forever |
| `--poll-interval-seconds` | 300 | Seconds between cycles |
| `--mongo-uri` | from .env | MongoDB connection string |
| `--mongo-db` | facebook_scraper | Database name |
| `--mongo-collection` | raw_posts | Collection name |

**parser.py:**
| Flag | Default | Description |
|------|---------|-------------|
| `--ollama-model` | llama3 | Ollama model name |
| `--batch-size` | 10 | Posts per batch |
| `--poll-interval` | 30 | Seconds between polls |
| `--once` | false | Single batch mode |

## MongoDB Collections

### `raw_posts` – Scraped Facebook posts
- `postId`, `permalink`, `author`, `content`, `timestamp`, `media[]`
- `parsed` (bool) – whether the parser has processed this post

### `listings` – Structured rental listings
- `title`, `propertyType`, `bhk`, `rentAmount`, `deposit`
- `location` (locality, area, city, landmark)
- `furnishing`, `amenities[]`, `tenantPreference`
- `contactInfo` (phone, whatsapp, name)
- `confidence` (0-1), `isRentalPost`, `media[]`

## Legacy JS Scraper

The original JavaScript scraper (`facebook-group-scraper.mjs`) is kept for reference. Use `npm run scrape` to run it.

## Notes

- Facebook frequently changes DOM structure. Selectors may need updates.
- Ollama must be running locally for the parser to work.
- The parser will retry failed posts on subsequent cycles.
