r"""
Detect historical reposts by scanning the image hash index.

For each pair of listings, counts matching images (Hamming distance <= 6).
If 2+ images match, marks the older listing as superseded by the newer one.

Usage:
  .venv\Scripts\python detect_historical_reposts.py --mongo-uri "mongodb://..." --mongo-db facebook_scraper --report-file ../reports/reposts_detected.json --dry-run

Options:
  --dry-run: Show what would be marked without committing to Mongo
  --report-file: JSON file for results (defaults to detected_reposts.json)
"""

import argparse
import json
import os
from collections import defaultdict
from pymongo import MongoClient
from bson import ObjectId

import config
from image_dedup import i64_to_u64, hamming, MATCH_THRESHOLD, MIN_MATCHED_IMAGES


def main():
    ap = argparse.ArgumentParser(description="Detect and mark historical reposts")
    ap.add_argument("--mongo-uri", default=config.MONGO_URI)
    ap.add_argument("--mongo-db", default=config.MONGO_DB)
    ap.add_argument("--listings-collection", default=config.LISTINGS_COLLECTION)
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    ap.add_argument("--report-file", default="detected_reposts.json")
    args = ap.parse_args()

    client = MongoClient(args.mongo_uri)
    db = client[args.mongo_db]
    listings_coll = db[args.listings_collection]
    hashes_coll = db["image_hashes"]

    print("Scanning hash index for historical reposts...")

    # Load all hashes grouped by listing
    listing_hashes = defaultdict(list)
    hash_cursor = hashes_coll.find({}, projection={"listingId": 1, "dhash": 1})
    for doc in hash_cursor:
        lid = str(doc.get("listingId"))
        dhash = doc.get("dhash")
        if dhash is not None:
            listing_hashes[lid].append(i64_to_u64(int(dhash)))

    print(f"Found {len(listing_hashes)} listings with hashes")

    # For each listing, find others with 2+ matching images
    marked = []
    examined = set()
    total_pairs = len(listing_hashes) * (len(listing_hashes) - 1) // 2
    pairs_examined = 0

    for lid_a in sorted(listing_hashes.keys()):
        for lid_b in sorted(listing_hashes.keys()):
            if lid_a >= lid_b or (lid_a, lid_b) in examined:
                continue
            examined.add((lid_a, lid_b))
            pairs_examined += 1
            if pairs_examined % 1000 == 0:
                print(f"  Examined {pairs_examined}/{total_pairs} pairs ({100*pairs_examined//total_pairs}%)")

            hashes_a = listing_hashes[lid_a]
            hashes_b = listing_hashes[lid_b]

            # Count matching images
            match_count = 0
            matched_pairs = []
            for h_a in hashes_a:
                for h_b in hashes_b:
                    dist = hamming(h_a, h_b)
                    if dist <= MATCH_THRESHOLD:
                        match_count += 1
                        matched_pairs.append({"hamming": dist})

            if match_count >= MIN_MATCHED_IMAGES:
                # Fetch listing metadata to determine which is older
                la = listings_coll.find_one({"_id": ObjectId(lid_a)}, {"createdAt": 1, "postedAt": 1, "title": 1})
                lb = listings_coll.find_one({"_id": ObjectId(lid_b)}, {"createdAt": 1, "postedAt": 1, "title": 1})

                if not la or not lb:
                    continue

                # Use createdAt (when we parsed it) or postedAt (when FB listed it) to determine age
                time_a = la.get("createdAt") or la.get("postedAt")
                time_b = lb.get("createdAt") or lb.get("postedAt")

                if time_a and time_b:
                    if time_a < time_b:
                        older_id, newer_id = lid_a, lid_b
                    else:
                        older_id, newer_id = lid_b, lid_a
                else:
                    # If no timestamp, use ObjectId (generated at insert)
                    if ObjectId(lid_a).generation_time < ObjectId(lid_b).generation_time:
                        older_id, newer_id = lid_a, lid_b
                    else:
                        older_id, newer_id = lid_b, lid_a

                item = {
                    "older_id": older_id,
                    "newer_id": newer_id,
                    "older_title": (la.get("title") if older_id == lid_a else lb.get("title")) or "",
                    "newer_title": (lb.get("title") if newer_id == lid_b else la.get("title")) or "",
                    "matched_images": match_count,
                    "matched_pairs": matched_pairs[:5],  # Include first 5 for audit
                }

                marked.append(item)

    print(f"Found {len(marked)} repost clusters (2+ matching images)")

    # Apply updates if not dry-run
    if not args.dry_run:
        for item in marked:
            try:
                listings_coll.update_one(
                    {"_id": ObjectId(item["older_id"])},
                    {"$set": {"isAvailable": False, "supersededBy": item["newer_id"]}},
                )
            except Exception as e:
                print(f"  Error marking {item['older_id']}: {e}")

        print(f"Marked {len(marked)} listings as superseded")
    else:
        print("Dry-run mode: no changes committed")

    # Write report
    os.makedirs(os.path.dirname(args.report_file) or ".", exist_ok=True)
    with open(args.report_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": {"total_clusters": len(marked), "dry_run": args.dry_run},
                "items": marked,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Report written to {args.report_file}")


if __name__ == "__main__":
    main()
