"""
Rentd LLM Parsing Service – Transforms raw Facebook posts into structured rental listings.
Uses Gemini API (gemini-3.1-flash-lite-preview) for fast, structured data extraction.
"""
import json, time, re, sys, argparse
from datetime import datetime, timezone

from google import genai
from google.genai import types
from pymongo import MongoClient

import config
from helpers import classify_media_url

# ── Structured output schema ────────────────────────────────────────────

VALID_AMENITIES = {
    "ac", "washing_machine", "refrigerator", "wifi", "parking", "gym",
    "swimming_pool", "power_backup", "security", "lift", "geyser",
    "water_purifier", "microwave", "tv", "bed", "wardrobe", "sofa",
    "dining_table", "modular_kitchen", "balcony", "club_house", "cctv",
    "gas_stove", "water_heater", "intercom", "rainwater_harvesting",
    "jogging_track", "garden", "play_area", "pet_area", "party_hall",
    "mini_theatre", "laundry"
}

AMENITY_ALIASES = {
    "air conditioner": "ac",
    "air conditioning": "ac",
    "fridge": "refrigerator",
    "fridge available": "refrigerator",
    "wifi internet": "wifi",
    "wi-fi": "wifi",
    "power backup": "power_backup",
    "backup power": "power_backup",
    "security guard": "security",
    "security guards": "security",
    "water filter": "water_purifier",
    "ro water": "water_purifier",
    "purifier": "water_purifier",
    "cupboard": "wardrobe",
    "cupboards": "wardrobe",
    "almirah": "wardrobe",
    "cupboard/wardrobe": "wardrobe",
    "modular kitchen": "modular_kitchen",
    "clubhouse": "club_house",
    "club house": "club_house",
    "playground": "play_area",
    "children play area": "play_area",
    "car parking": "parking",
    "bike parking": "parking",
    "two wheeler parking": "parking",
    "four wheeler parking": "parking",
    "gated security": "security",
    "water heater": "water_heater",
}

TRI_STATE_TRUE = {"yes", "true", "y", "1", "allowed", "available"}
TRI_STATE_FALSE = {"no", "false", "n", "0", "not allowed", "unavailable"}
TRI_STATE_UNKNOWN = {"unknown", "not mentioned", "na", "n/a", "", "null", "none"}

AMENITY_ENUM_HINT = ", ".join(sorted(VALID_AMENITIES))

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "is_rental_post": {"type": "boolean", "description": "true if this is a rental listing, false if looking for flat, selling, or unrelated"},
        "title": {"type": "string", "description": "Short descriptive title for the listing"},
        "property_type": {"type": "string", "enum": ["apartment", "house", "pg", "villa", "studio", "flat", "other"]},
        "bhk": {"type": "string", "description": "1, 1.5, 2, 2.5, 3, 4, 5+, or empty if unknown"},
        "rent_min": {"type": "integer", "description": "Monthly rent minimum in INR, 0 if unknown"},
        "rent_max": {"type": "integer", "description": "Monthly rent maximum in INR, 0 if unknown"},
        "deposit_amount": {"type": "integer", "description": "Deposit amount in INR, 0 if unknown"},
        "deposit_months": {"type": "integer", "description": "Number of months deposit, 0 if unknown"},
        "locality": {"type": "string", "description": "Specific area/colony name"},
        "area": {"type": "string", "description": "Broader area name"},
        "city": {"type": "string", "description": "City name"},
        "landmark": {"type": "string", "description": "Nearby landmark if mentioned"},
        "furnishing": {"type": "string", "enum": ["fully_furnished", "semi_furnished", "unfurnished", "unknown"]},
        "amenities": {"type": "array", "items": {"type": "string", "enum": list(VALID_AMENITIES)}, "description": "List of recognized amenities."},
        "other_amenities": {"type": "array", "items": {"type": "string"}, "description": "Any additional amenities mentioned that are not in the recognized list"},
        "sqft": {"type": "integer", "description": "Area in sqft, 0 if unknown"},
        "floor_info": {"type": "string", "description": "Floor number or range if mentioned"},
        "tenant_gender": {"type": "string", "enum": ["male", "female", "any", "family", "unknown"]},
        "vegetarian_only": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "bachelors_allowed": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "available_from": {"type": "string", "description": "YYYY-MM-DD or empty"},
        "contact_phones": {"type": "array", "items": {"type": "string"}, "description": "Phone numbers found in text"},
        "contact_whatsapp": {"type": "array", "items": {"type": "string"}, "description": "WhatsApp numbers found"},
        "contact_name": {"type": "string", "description": "Name of contact person"},
        "is_agent": {"type": "string", "enum": ["yes", "no", "unknown"], "description": "yes if poster is an agent/broker, no if owner, unknown if unclear"},
        "parking": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "pets_allowed": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "summary": {"type": "string", "description": "2-3 sentence summary of the listing"},
        "confidence": {"type": "number", "description": "0.0-1.0 confidence score. 1.0=all key fields extracted, 0.5=partial, 0.1=very little"}
    },
    "required": ["is_rental_post", "title", "property_type", "confidence", "summary"]
}

SYSTEM_PROMPT = """You are a rental listing extraction assistant for the Indian housing market.
Your core task is to process raw social media posts about rental properties and extract structured information.

Rules:
- Set is_rental_post=false for non-rental posts (looking for flat, selling, unrelated).
- Extract phone numbers from text, even if embedded in sentences.
- Recognize common Indian rental terms: BHK, lakh, k, crore, society, colony.
- If rent is "15k" interpret as 15000, "1.5L" as 150000.
- For PG/hostel posts, property_type should be "pg".
- amenities must ONLY use this fixed list in the amenities array: """ + AMENITY_ENUM_HINT + """
- if any amenity is mentioned but not in that list, put it in other_amenities (do not drop it).
- is_agent: 'yes' only if explicitly broker/agent/commission/consultancy. 'no' only if explicitly owner/no brokerage/no broker. 'unknown' if not explicit.
- confidence: 1.0 = all key fields extracted, 0.5 = partial info, 0.1 = very little info.
- Use empty string for unknown text fields, 0 for unknown numbers.

Constraints:
- You must NOT use your own knowledge to fill in missing information. Rely ONLY on the facts directly mentioned in the provided text.
- For parking, pets_allowed, bachelors_allowed, vegetarian_only: Do NOT guess or infer. If not explicitly mentioned, you MUST output 'unknown'.
- Do NOT output 'yes' or 'no' for the above fields unless it is clearly stated in the text.
"""

# ── Gemini API ───────────────────────────────────────────────────────────

_client = None

def get_client():
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            print("Error: GEMINI_API_KEY is required. Set it in .env")
            sys.exit(1)
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def call_gemini(content: str, author: str, timestamp: str) -> dict | None:
    """Send post to Gemini and get structured JSON response with retries."""
    prompt = f"""Extract rental listing information from this Facebook group post:

Author: {author or 'Unknown'}
Posted: {timestamp or 'Unknown'}
Content:
{content[:4000]}"""

    client = get_client()
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_json_schema": LISTING_SCHEMA,
                    "temperature": 1.0,
                },
            )

            if not response.text:
                print(" ⚠ Empty response from Gemini")
                return None

            raw_text = response.text.strip()
            # If wrapped in markdown blocks, extract
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
            if match:
                raw_text = match.group(1).strip()
            
            # Extract just the top-level JSON object to avoid trailing garbage
            start = raw_text.find('{')
            end = raw_text.rfind('}')
            if start != -1 and end != -1:
                raw_text = raw_text[start:end+1]

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as jde:
                print(f" ⚠ JSON parse failed: {jde}. Raw: {raw_text[:100]}...")
                return None

        except Exception as e:
            err_str = str(e).upper()
            is_transient = any(code in err_str for code in ["503", "500", "429", "UNAVAILABLE", "DEADLINE_EXCEEDED", "TIME", "TIMEOUT"])
            
            
            if is_transient and attempt < max_retries - 1:
                # Check if Google tells us exactly how long to wait
                delay_match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE)
                actual_delay = float(delay_match.group(1)) + 1.0 if delay_match else retry_delay
                
                print(f" ⏳ {e} - Retrying in {actual_delay:.1f}s... ", end="", flush=True)
                time.sleep(actual_delay)
                retry_delay = actual_delay * 1.5  # Exponential backoff based on actual delay
                continue
            else:
                print(f" ✗ Gemini error: {e}")
                return None
    return None

def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9_\s-]", "", (value or "").strip().lower())

def _to_tri_state(value) -> str:
    norm = _normalize_token(str(value)) if value is not None else ""
    if norm in TRI_STATE_TRUE:
        return "yes"
    if norm in TRI_STATE_FALSE:
        return "no"
    if norm in TRI_STATE_UNKNOWN:
        return "unknown"
    return "unknown"

def _enum_or_unknown(value: str, allowed: set[str], default: str = "unknown") -> str:
    val = _normalize_token(value)
    return val if val in allowed else default

def _normalize_amenity(value: str) -> str:
    token = _normalize_token(value).replace(" ", "_")
    if token in VALID_AMENITIES:
        return token
    alias_key = _normalize_token(value)
    mapped = AMENITY_ALIASES.get(alias_key)
    if mapped:
        return mapped
    return ""

def _normalize_amenities(llm_data: dict) -> tuple[list[str], list[str]]:
    canonical = set()
    other = set()
    for raw in (llm_data.get("amenities") or []):
        if not isinstance(raw, str):
            continue
        mapped = _normalize_amenity(raw)
        if mapped:
            canonical.add(mapped)
        else:
            cleaned = _normalize_token(raw)
            if cleaned:
                other.add(cleaned)
    for raw in (llm_data.get("other_amenities") or []):
        if not isinstance(raw, str):
            continue
        mapped = _normalize_amenity(raw)
        if mapped:
            canonical.add(mapped)
        else:
            cleaned = _normalize_token(raw)
            if cleaned:
                other.add(cleaned)
    return sorted(canonical), sorted(other)

def _policy_from_text(text: str, yes_patterns: list[str], no_patterns: list[str]) -> str:
    if not text:
        return "unknown"
    lower = text.lower()
    if any(re.search(pattern, lower) for pattern in no_patterns):
        return "no"
    if any(re.search(pattern, lower) for pattern in yes_patterns):
        return "yes"
    return "unknown"

def _resolve_is_agent(llm_value, content: str) -> str:
    llm_state = _to_tri_state(llm_value)
    if llm_state != "unknown":
        return llm_state
    return _policy_from_text(
        content or "",
        yes_patterns=[
            r"\bagent\b", r"\bbroker\b", r"\bbrokerage\b", r"\bcommission\b",
            r"consult(ing|ancy)\s+fees?"
        ],
        no_patterns=[
            r"\bowner\b", r"\bno\s+broker(age)?\b", r"\bno\s+broker\b",
            r"\bzero\s+broker(age)?\b", r"\bwithout\s+broker(age)?\b"
        ],
    )

def _resolve_policy(llm_value, content: str, yes_patterns: list[str], no_patterns: list[str]) -> str:
    llm_state = _to_tri_state(llm_value)
    if llm_state != "unknown":
        return llm_state
    return _policy_from_text(content or "", yes_patterns=yes_patterns, no_patterns=no_patterns)

# ── Build listing document ───────────────────────────────────────────────

def _map_enum(val: str) -> bool | None:
    if val == "yes":
        return True
    if val == "no":
        return False
    return None

def build_listing(raw_post: dict, llm_data: dict) -> dict:
    """Construct a structured listing document from raw post + LLM output."""
    now = datetime.now(timezone.utc)
    content = raw_post.get("content", "") or ""

    # Normalize amenities against fixed taxonomy
    amenities, other_amenities = _normalize_amenities(llm_data)

    # Strict tri-state policy resolution: explicit yes/no, else unknown.
    is_agent_state = _resolve_is_agent(llm_data.get("is_agent"), content)
    parking_state = _resolve_policy(
        llm_data.get("parking"),
        content,
        yes_patterns=[r"\bparking\b", r"\bcar parking\b", r"\bbike parking\b", r"\bcovered parking\b"],
        no_patterns=[r"\bno parking\b", r"\bparking not available\b", r"\bwithout parking\b"],
    )
    pets_state = _resolve_policy(
        llm_data.get("pets_allowed"),
        content,
        yes_patterns=[r"\bpets? allowed\b", r"\bpet friendly\b"],
        no_patterns=[r"\bno pets?\b", r"\bpets? not allowed\b", r"\bnot pet friendly\b"],
    )
    bachelors_state = _resolve_policy(
        llm_data.get("bachelors_allowed"),
        content,
        yes_patterns=[r"\bbachelors? allowed\b", r"\bbachelor friendly\b"],
        no_patterns=[r"\bno bachelors?\b", r"\bbachelors? not allowed\b"],
    )
    vegetarian_state = _resolve_policy(
        llm_data.get("vegetarian_only"),
        content,
        yes_patterns=[r"\bveg(etarian)? only\b", r"\bvegetarian only\b"],
        no_patterns=[r"\bnon[-\s]?veg allowed\b", r"\bnon[-\s]?vegetarian allowed\b"],
    )

    # Filter media to direct, renderable assets only.
    media = []
    seen_media = set()
    for m in (raw_post.get("media") or []):
        url = m.get("url", "")
        if not url or not url.startswith("http"): continue
        if re.search(r"facebook\.com/photo(\.php|/)|facebook\.com/.*/photos/|facebook\.com/photos/", url, re.I):
            continue

        media_type = classify_media_url(url, str(m.get("type", "")))
        if not media_type:
            # Some video links may not include useful path hints.
            if str(m.get("type", "")).lower() == "video" and re.search(r"\.(mp4|m3u8)(\?|$)", url, re.I):
                media_type = "video"
            else:
                continue

        media_key = re.sub(r"[?#].*$", "", url)
        if media_key in seen_media:
            continue

        # Ignore tiny profile pictures and unsupported .kf keyframes
        lower_url = url.lower()
        if re.search(r"\.kf(\?|$)", lower_url) or re.search(r"_[sp]\d+x\d+_", lower_url):
            continue

        w = m.get("width") or 0
        h = m.get("height") or 0
        if media_type == "image" and w and h and w < 150 and h < 150: continue

        seen_media.add(media_key)
        media.append({"type": media_type, "url": url,
                       "width": m.get("width"), "height": m.get("height")})

    # Build rent range
    rent_min = llm_data.get("rent_min") or 0
    rent_max = llm_data.get("rent_max") or 0
    if rent_min and not rent_max: rent_max = rent_min
    if rent_max and not rent_min: rent_min = rent_max

    tenant_gender = _enum_or_unknown(
        llm_data.get("tenant_gender", ""),
        {"male", "female", "any", "family", "unknown"},
        default="unknown",
    )
    furnishing = _enum_or_unknown(
        llm_data.get("furnishing", ""),
        {"fully_furnished", "semi_furnished", "unfurnished", "unknown"},
        default="unknown",
    )
    property_type = _enum_or_unknown(
        llm_data.get("property_type", ""),
        {"apartment", "house", "pg", "villa", "studio", "flat", "other"},
        default="other",
    )

    return {
        "sourcePostId": raw_post.get("postId", ""),
        "permalink": raw_post.get("permalink", ""),
        "author": raw_post.get("author", ""),
        "rawContent": content,
        "title": llm_data.get("title") or "",
        "summary": llm_data.get("summary") or "",
        "propertyType": property_type,
        "bhk": llm_data.get("bhk") or None,
        "rentAmount": {"min": rent_min or None, "max": rent_max or None, "currency": "INR"},
        "deposit": {"amount": llm_data.get("deposit_amount") or None, "months": llm_data.get("deposit_months") or None},
        "sqft": llm_data.get("sqft") or None,
        "floor": llm_data.get("floor_info") or None,
        "location": {
            "locality": llm_data.get("locality") or "",
            "area": llm_data.get("area") or "",
            "city": llm_data.get("city") or "",
            "landmark": llm_data.get("landmark") or ""
        },
        "furnishing": furnishing if furnishing != "unknown" else None,
        "amenities": amenities,
        "other_amenities": other_amenities,
        "tenantPreference": {
            "gender": tenant_gender if tenant_gender != "unknown" else None,
            "vegetarian": _map_enum(vegetarian_state),
            "bachelors": _map_enum(bachelors_state)
        },
        "parking": _map_enum(parking_state),
        "petsAllowed": _map_enum(pets_state),
        "availableFrom": llm_data.get("available_from") or None,
        "contactInfo": {
            "phone": llm_data.get("contact_phones") or [],
            "whatsapp": llm_data.get("contact_whatsapp") or [],
            "name": llm_data.get("contact_name") or ""
        },
        "isAgent": _map_enum(is_agent_state),
        "media": media[:12],
        "confidence": max(0.0, min(1.0, float(llm_data.get("confidence", 0.5)))),
        "isRentalPost": llm_data.get("is_rental_post", True),
        "postedAt": raw_post.get("timestamp", ""),
        "scrapedAt": raw_post.get("scrapedAt", ""),
        "parsedAt": now.isoformat(),
        "groupUrl": raw_post.get("groupUrl", ""),
        "schemaVersion": "listing.v2",
        "policyResolution": {
            "isAgent": is_agent_state,
            "parking": parking_state,
            "petsAllowed": pets_state,
            "bachelorsAllowed": bachelors_state,
            "vegetarianOnly": vegetarian_state,
        },
        "updatedAt": now,
    }

# ── Main loop ────────────────────────────────────────────────────────────

def run_parser(mongo_uri: str, db_name: str, raw_coll: str, listings_coll: str,
               batch_size: int, poll_interval: int, once: bool = False):
    """Continuously poll raw_posts for unparsed documents and process them."""
    if not mongo_uri:
        print("Error: MONGO_URI is required for the parser.")
        sys.exit(1)

    client = MongoClient(mongo_uri)
    db = client[db_name]
    raw_collection = db[raw_coll]
    listing_collection = db[listings_coll]

    # Create indexes on listings
    listing_collection.create_index("sourcePostId", unique=True, sparse=True)
    listing_collection.create_index("permalink", sparse=True)
    listing_collection.create_index([("location.locality", 1)])
    listing_collection.create_index([("rentAmount.min", 1)])
    listing_collection.create_index([("bhk", 1)])
    listing_collection.create_index([("isRentalPost", 1)])
    listing_collection.create_index([("confidence", -1)])
    listing_collection.create_index([("parsedAt", -1)])

    print(f"Parser connected to MongoDB: {db_name}")
    print(f"  Raw posts: {raw_coll} → Listings: {listings_coll}")
    print(f"  Gemini model: {config.GEMINI_MODEL}")
    print(f"  Batch size: {batch_size}, Poll interval: {poll_interval}s")

    cycle = 0
    while True:
        cycle += 1
        unparsed = list(raw_collection.find(
            {"$or": [{"parsed": False}, {"parsed": {"$exists": False}}]},
            sort=[("scrapedAt", -1)]
        ).limit(batch_size))

        if not unparsed:
            if once:
                print("No unparsed posts found. Exiting.")
                break
            print(f"[Cycle {cycle}] No unparsed posts. Waiting {poll_interval}s...")
            time.sleep(poll_interval)
            continue

        print(f"\n[Cycle {cycle}] Processing {len(unparsed)} posts...")

        parsed_count = 0
        rental_count = 0
        error_count = 0

        for i, post in enumerate(unparsed, 1):
            post_id = post.get("postId", "unknown")
            author = post.get("author", "Unknown")
            content = post.get("content", "")

            if not content or len(content.strip()) < 10:
                raw_collection.update_one({"_id": post["_id"]}, {"$set": {"parsed": True, "parseSkipped": True}})
                print(f"  [{i}/{len(unparsed)}] Skipped (no content): {post_id}")
                continue

            print(f"  [{i}/{len(unparsed)}] Parsing post by {author[:30]}... ", end="", flush=True)

            llm_data = call_gemini(content, author, post.get("timestamp", ""))

            if llm_data is None:
                error_count += 1
                print("FAILED")
                # Rate limit: back off a bit
                time.sleep(2)
                continue

            listing = build_listing(post, llm_data)
            parsed_count += 1

            if listing["isRentalPost"]:
                rental_count += 1
                filter_doc = {"sourcePostId": listing["sourcePostId"]} if listing["sourcePostId"] else \
                             {"permalink": listing["permalink"]} if listing["permalink"] else \
                             {"rawContent": listing["rawContent"][:500]}

                listing_collection.update_one(
                    filter_doc,
                    {"$set": listing, "$setOnInsert": {"createdAt": datetime.now(timezone.utc)}},
                    upsert=True
                )
                conf = listing["confidence"]
                conf_bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
                loc = listing['location']['locality'] or listing['location']['area'] or '?'
                rent = listing['rentAmount']['min']
                print(f"✓ RENTAL [{conf_bar}] {listing['bhk'] or '?'}BHK {loc} ₹{rent or '?'}")
            else:
                print(f"✗ Not rental")

            # Mark raw post as parsed
            raw_collection.update_one(
                {"_id": post["_id"]},
                {"$set": {"parsed": True, "parsedAt": datetime.now(timezone.utc).isoformat(),
                          "isRentalPost": listing["isRentalPost"]}}
            )

        print(f"\n[Cycle {cycle}] Done: {parsed_count} parsed, {rental_count} rentals, {error_count} errors")

        if once:
            break

        if error_count == len(unparsed):
            print(f"All posts failed. Waiting {poll_interval * 2}s...")
            time.sleep(poll_interval * 2)
        else:
            time.sleep(poll_interval)

    client.close()
    print("Parser stopped.")


def main():
    ap = argparse.ArgumentParser(description="Rentd Gemini Parsing Service")
    ap.add_argument("--mongo-uri", default=config.MONGO_URI)
    ap.add_argument("--mongo-db", default=config.MONGO_DB)
    ap.add_argument("--raw-collection", default=config.RAW_POSTS_COLLECTION)
    ap.add_argument("--listings-collection", default=config.LISTINGS_COLLECTION)
    ap.add_argument("--batch-size", type=int, default=config.PARSER_BATCH_SIZE)
    ap.add_argument("--poll-interval", type=int, default=config.PARSER_POLL_INTERVAL)
    ap.add_argument("--gemini-model", default=config.GEMINI_MODEL)
    ap.add_argument("--once", action="store_true", help="Process one batch and exit")
    args = ap.parse_args()

    config.GEMINI_MODEL = args.gemini_model

    run_parser(
        mongo_uri=args.mongo_uri,
        db_name=args.mongo_db,
        raw_coll=args.raw_collection,
        listings_coll=args.listings_collection,
        batch_size=args.batch_size,
        poll_interval=args.poll_interval,
        once=args.once
    )


if __name__ == "__main__":
    main()
