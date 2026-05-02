r"""
Reindex existing listings: compute and store dHash for each image and produce
a report of listings marked unavailable / superseded.

Usage:
    .venv\Scripts\python reindex_hashes.py --mongo-uri "mongodb://..." --mongo-db facebook_scraper --report-file ../reports/superseded_report.json

The script calls `ensure_hash_index` and `store_hashes` from `image_dedup.py`.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from pymongo import UpdateOne
from pymongo import MongoClient
import config
from image_dedup import bucket_of, compute_dhash, ensure_hash_index, u64_to_i64


def _hash_image(url: str):
    dhash = compute_dhash(url)
    if dhash is None:
        return None
    return {
        "imageUrl": url,
        "dhash": u64_to_i64(dhash),
        "bucket": bucket_of(dhash),
    }


def build_superseded_report(listings_coll):
    report = []
    superseded_cursor = listings_coll.find(
        {"$or": [{"isAvailable": False}, {"supersededBy": {"$exists": True, "$ne": ""}}]},
        projection={"_id": 1, "title": 1, "permalink": 1, "supersededBy": 1, "media": 1},
    )

    for doc in superseded_cursor:
        item = {
            "listingId": str(doc.get("_id")),
            "title": doc.get("title") or "",
            "permalink": doc.get("permalink") or "",
            "supersededBy": str(doc.get("supersededBy") or ""),
            "mediaUrls": [m.get("url") for m in (doc.get("media") or []) if m and m.get("type") == "image" and m.get("url")],
        }
        if item["supersededBy"]:
            try:
                from bson import ObjectId

                target = listings_coll.find_one({"_id": ObjectId(item["supersededBy"])}, {"permalink": 1, "title": 1})
                if target:
                    item["supersededBy_permalink"] = target.get("permalink") or ""
                    item["supersededBy_title"] = target.get("title") or ""
            except Exception:
                pass

        report.append(item)

    return report


def write_report(out_path: str, report: list, total_listings: int, total_hashes: int) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": {
                    "listings_scanned": total_listings,
                    "hashes_stored": total_hashes,
                    "superseded_count": len(report),
                },
                "items": report,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mongo-uri", default=config.MONGO_URI)
    ap.add_argument("--mongo-db", default=config.MONGO_DB)
    ap.add_argument("--listings-collection", default=config.LISTINGS_COLLECTION)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--workers", type=int, default=min(32, (os.cpu_count() or 4) + 8))
    ap.add_argument("--write-batch-size", type=int, default=500)
    ap.add_argument("--reset-hashes", action="store_true", help="Drop all existing image hashes before rebuilding")
    ap.add_argument("--report-file", default="superseded_report.json")
    ap.add_argument("--only-unindexed", action="store_true", help="Skip images already present in image_hashes collection")
    args = ap.parse_args()

    client = MongoClient(args.mongo_uri)
    db = client[args.mongo_db]
    listings_coll = db[args.listings_collection]

    # Ensure indexes exist
    ensure_hash_index(db)
    image_hashes_coll = db["image_hashes"]

    if args.reset_hashes:
        deleted = image_hashes_coll.delete_many({}).deleted_count
        print(f"Reset image hash collection ({deleted} documents deleted)")

    report = build_superseded_report(listings_coll)
    write_report(args.report_file, report, 0, 0)
    print(f"Initial report written to {args.report_file} ({len(report)} superseded/unavailable listings)")

    print(f"Reindex: scanning listings for images (workers={args.workers}, write_batch={args.write_batch_size})...")

    query = {"media": {"$exists": True, "$ne": []}}
    cursor = listings_coll.find(query, projection={"media": 1, "permalink": 1, "title": 1}).batch_size(max(1, args.batch_size))

    total_listings = 0
    total_hashes = 0
    pending_writes = []
    def flush_writes(reason: str = "batch"):
        nonlocal total_hashes, pending_writes
        if not pending_writes:
            return 0
        pending_count = len(pending_writes)
        result = image_hashes_coll.bulk_write(pending_writes, ordered=False)
        stored = result.upserted_count + result.modified_count
        total_hashes += stored
        pending_writes = []
        print(f"  Flushed {pending_count} hash writes to Mongo ({stored} stored, reason={reason})")
        return stored

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for doc in cursor:
            total_listings += 1
            lid = str(doc.get("_id"))
            media = doc.get("media") or []
            image_urls = [m.get("url") for m in media if m and m.get("type") == "image" and m.get("url")]
            if len(image_urls) < 2:
                continue

            future_map = {pool.submit(_hash_image, url): url for url in image_urls}
            results = []
            for future in as_completed(future_map):
                try:
                    value = future.result()
                except Exception:
                    value = None
                if value:
                    value["listingId"] = lid
                    results.append(value)

            if results:
                pending_writes.extend(
                    UpdateOne({"imageUrl": item["imageUrl"]}, {"$set": {**item, "listingId": lid}}, upsert=True)
                    for item in results
                )
                if len(pending_writes) >= args.write_batch_size:
                    flush_writes(reason="write-batch-size")
                print(f"  Hashed {len(results)} images for listing {lid}")

    flush_writes(reason="final")

    print(f"Done hashing: processed {total_listings} listings, stored {total_hashes} new hashes")

    # Refresh the report summary at the end so the final JSON includes actual hash stats.
    write_report(args.report_file, report, total_listings, total_hashes)
    print(f"Report updated at {args.report_file} ({len(report)} superseded/unavailable listings)")


if __name__ == "__main__":
    main()
