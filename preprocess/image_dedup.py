"""
Image deduplication for Rentd using dHash (difference hash) with bucket-based lookup.

Algorithm (O(1)-like per image):
  1. Download image → resize to 9×8 grayscale → compute 64-bit dHash
  2. Store hash in MongoDB with first-byte bucket (0-255)
  3. On new listing: compute hashes → look up bucket → Hamming distance
  4. Match threshold ≤ 6 bits → treat as repost
  5. If repost: mark old listing unavailable, allow new one in
"""

import io
import struct
import hashlib
import urllib.request
import urllib.error
from typing import Optional

# ── Optional fast dependency, falls back to stdlib ────────────────────────
try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# ── Constants ─────────────────────────────────────────────────────────────

HASH_BITS = 64          # 8×8 dHash → 64 bits stored as int64
BUCKET_BITS = 8         # First byte = 256 buckets
MATCH_THRESHOLD = 6     # ≤ 6 bit difference → likely same image
MIN_MATCHED_IMAGES = 2   # Require at least 2 matching images to treat as repost
DOWNLOAD_TIMEOUT = 8    # seconds
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024   # 5 MB cap

# MongoDB collection name for hash index
DHASH_COLLECTION = "image_hashes"

U64_MASK = (1 << 64) - 1
I64_SIGN_BIT = 1 << 63

# ── dHash computation ─────────────────────────────────────────────────────

def _dhash_pil(url: str) -> Optional[int]:
    """Download image and compute 64-bit dHash using Pillow."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            data = resp.read(MAX_DOWNLOAD_BYTES)
        img = PILImage.open(io.BytesIO(data)).convert("L").resize((9, 8))
        pixels = list(img.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                left = pixels[row * 9 + col]
                right = pixels[row * 9 + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return bits
    except Exception:
        return None


def _dhash_pure(url: str) -> Optional[int]:
    """
    Pure-stdlib fallback using PPM/BMP header parsing.
    Supports only JPEG/PNG via a minimal decode — less accurate than PIL.
    Returns None if image can't be processed.
    """
    # We can't decode JPEG without PIL reliably, so return None.
    # The caller will skip dedup for this image gracefully.
    return None


def compute_dhash(url: str) -> Optional[int]:
    """Return 64-bit dHash integer for the image at `url`, or None on failure."""
    if _HAS_PIL:
        return _dhash_pil(url)
    return _dhash_pure(url)


def hamming(a: int, b: int) -> int:
    """Count differing bits between two 64-bit integers."""
    xor = a ^ b
    count = 0
    while xor:
        count += xor & 1
        xor >>= 1
    return count


def bucket_of(dhash: int) -> int:
    """Extract the first byte of the hash as the bucket id (0-255)."""
    return (dhash >> 56) & 0xFF


def u64_to_i64(value: int) -> int:
    """Convert an unsigned 64-bit int to a MongoDB-safe signed int64."""
    value &= U64_MASK
    return value - (1 << 64) if value & I64_SIGN_BIT else value


def i64_to_u64(value: int) -> int:
    """Convert a stored signed int64 back to an unsigned 64-bit int."""
    return value & U64_MASK


# ── MongoDB index management ──────────────────────────────────────────────

def ensure_hash_index(db) -> None:
    """Create indexes on the image_hashes collection if they don't exist."""
    coll = db[DHASH_COLLECTION]
    coll.create_index("bucket")
    coll.create_index("listingId")
    coll.create_index("imageUrl", unique=True, sparse=True)


def store_hashes(db, listing_id: str, image_urls: list[str]) -> int:
    """
    Compute dHash for each image URL and store in the hash collection.
    Returns number of hashes stored.
    """
    coll = db[DHASH_COLLECTION]
    stored = 0
    for url in image_urls:
        h = compute_dhash(url)
        if h is None:
            continue
        doc = {
            "listingId": listing_id,
            "imageUrl": url,
            "dhash": u64_to_i64(h),
            "bucket": bucket_of(h),
        }
        try:
            coll.update_one({"imageUrl": url}, {"$set": doc}, upsert=True)
            stored += 1
        except Exception:
            pass
    return stored


# ── Duplicate detection ───────────────────────────────────────────────────

def find_duplicate_listing(db, image_urls: list[str], exclude_listing_id: str = "") -> Optional[str]:
    """
    For a new listing's images, search the hash index for a match.
    
    Returns the listingId of the matched existing listing, or None if no match.
    Uses bucket lookup to avoid brute-force scanning the entire collection.
    """
    if len(image_urls) < MIN_MATCHED_IMAGES:
        return None

    hash_coll = db[DHASH_COLLECTION]
    match_counts: dict[str, int] = {}

    for url in image_urls:
        h = compute_dhash(url)
        if h is None:
            continue

        bucket = bucket_of(h)

        # Only compare within the same bucket (±1 for edge cases near bucket boundary)
        candidate_buckets = list({bucket, (bucket - 1) & 0xFF, (bucket + 1) & 0xFF})
        candidates = list(hash_coll.find({"bucket": {"$in": candidate_buckets}}))

        for candidate in candidates:
            # Skip self-comparison
            if exclude_listing_id and candidate.get("listingId") == exclude_listing_id:
                continue

            candidate_hash = candidate.get("dhash")
            if candidate_hash is None:
                continue

            dist = hamming(h, i64_to_u64(int(candidate_hash)))
            if dist <= MATCH_THRESHOLD:
                listing_id = str(candidate["listingId"])
                match_counts[listing_id] = match_counts.get(listing_id, 0) + 1
                if match_counts[listing_id] >= MIN_MATCHED_IMAGES:
                    return listing_id

    return None


# ── High-level integration function ──────────────────────────────────────

def check_and_handle_repost(db, new_listing: dict, listing_collection) -> Optional[str]:
    """
    Called before inserting a new listing. Checks if any of its images
    match an existing listing. If so:
      - Marks the OLD listing as isAvailable=False (it's a repost)
      - Returns the old listingId (so the caller knows a replacement happened)
      - Returns None if this is a genuinely new listing

    The caller should proceed to insert/update the new listing regardless.
    """
    media = new_listing.get("media") or []
    image_urls = [m["url"] for m in media if m.get("type") == "image" and m.get("url")]

    if not image_urls:
        return None

    matched_id = find_duplicate_listing(db, image_urls)
    if matched_id is None:
        return None

    # Mark the old listing as unavailable (reposted / superseded)
    try:
        from bson import ObjectId
        listing_collection.update_one(
            {"_id": ObjectId(matched_id)},
            {"$set": {"isAvailable": False, "supersededBy": new_listing.get("sourcePostId", "")}}
        )
        print(f"    ♻ Repost detected — marked old listing {matched_id} as unavailable")
    except Exception as e:
        print(f"    ⚠ Could not mark duplicate: {e}")

    return matched_id
