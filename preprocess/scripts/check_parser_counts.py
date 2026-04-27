#!/usr/bin/env python3
"""
Compare parser progress between raw_posts and listings collections.

Usage:
  python scripts/check_parser_counts.py
  python scripts/check_parser_counts.py --sample-size 25
  python scripts/check_parser_counts.py --mongo-db facebook_scraper
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from pymongo import MongoClient

# Allow importing preprocess/config.py when run from scripts/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # type: ignore  # noqa: E402


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def unique_non_empty_strings(cursor: Iterable[dict], field: str) -> set[str]:
    values: set[str] = set()
    for doc in cursor:
        value = clean_text(doc.get(field))
        if value:
            values.add(value)
    return values


def print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check count drift between raw_posts parsing progress and listings writes"
    )
    parser.add_argument("--mongo-uri", default=config.MONGO_URI)
    parser.add_argument("--mongo-db", default=config.MONGO_DB)
    parser.add_argument("--raw-collection", default=config.RAW_POSTS_COLLECTION)
    parser.add_argument("--listings-collection", default=config.LISTINGS_COLLECTION)
    parser.add_argument(
        "--sample-size",
        type=int,
        default=15,
        help="How many missing IDs/permalinks to print",
    )
    args = parser.parse_args()

    if not args.mongo_uri:
        print("Error: --mongo-uri is required (or set MONGO_URI in preprocess/.env)")
        return 2

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        print(f"Error: could not connect to MongoDB: {exc}")
        return 2

    db = client[args.mongo_db]
    raw = db[args.raw_collection]
    listings = db[args.listings_collection]

    unparsed_query = {"$or": [{"parsed": False}, {"parsed": {"$exists": False}}]}
    parsed_query = {"parsed": True}

    raw_total = raw.count_documents({})
    raw_parsed = raw.count_documents(parsed_query)
    raw_unparsed = raw.count_documents(unparsed_query)
    raw_parse_skipped = raw.count_documents({"parseSkipped": True})
    raw_parsed_rental_true = raw.count_documents({"parsed": True, "isRentalPost": True})
    raw_parsed_rental_false = raw.count_documents({"parsed": True, "isRentalPost": False})

    listings_total = listings.count_documents({})
    listings_rental_true = listings.count_documents({"isRentalPost": True})
    listings_rental_false = listings.count_documents({"isRentalPost": False})
    listings_feed_visible = listings.count_documents(
        {"isRentalPost": True, "confidence": {"$gte": 0.5}}
    )

    raw_parsed_post_ids = unique_non_empty_strings(
        raw.find(parsed_query, {"postId": 1, "_id": 0}),
        "postId",
    )
    raw_all_post_ids = unique_non_empty_strings(
        raw.find({}, {"postId": 1, "_id": 0}),
        "postId",
    )
    raw_parsed_rental_post_ids = unique_non_empty_strings(
        raw.find({"parsed": True, "isRentalPost": True}, {"postId": 1, "_id": 0}),
        "postId",
    )
    listings_source_post_ids = unique_non_empty_strings(
        listings.find({}, {"sourcePostId": 1, "_id": 0}),
        "sourcePostId",
    )

    raw_parsed_rental_permalinks = unique_non_empty_strings(
        raw.find({"parsed": True, "isRentalPost": True}, {"permalink": 1, "_id": 0}),
        "permalink",
    )
    listings_permalinks = unique_non_empty_strings(
        listings.find({}, {"permalink": 1, "_id": 0}),
        "permalink",
    )

    missing_rental_post_ids = sorted(raw_parsed_rental_post_ids - listings_source_post_ids)
    missing_rental_permalinks = sorted(raw_parsed_rental_permalinks - listings_permalinks)
    listings_missing_in_raw = sorted(listings_source_post_ids - raw_all_post_ids)

    raw_parsed_no_post_id = raw.count_documents({"parsed": True, "$or": [{"postId": ""}, {"postId": {"$exists": False}}]})
    raw_parsed_rental_no_post_id = raw.count_documents(
        {
            "parsed": True,
            "isRentalPost": True,
            "$or": [{"postId": ""}, {"postId": {"$exists": False}}],
        }
    )

    print("Mongo parser consistency report")
    print(f"Database: {args.mongo_db}")
    print(f"Collections: {args.raw_collection} -> {args.listings_collection}")

    print_section("raw_posts")
    print(f"total: {raw_total}")
    print(f"parsed=true: {raw_parsed}")
    print(f"unparsed (parser query): {raw_unparsed}")
    print(f"parseSkipped=true: {raw_parse_skipped}")
    print(f"parsed + isRentalPost=true: {raw_parsed_rental_true}")
    print(f"parsed + isRentalPost=false: {raw_parsed_rental_false}")
    print(f"parsed with empty/missing postId: {raw_parsed_no_post_id}")
    print(f"parsed rentals with empty/missing postId: {raw_parsed_rental_no_post_id}")

    print_section("listings")
    print(f"total: {listings_total}")
    print(f"isRentalPost=true: {listings_rental_true}")
    print(f"isRentalPost=false: {listings_rental_false}")
    print(f"feed-visible (isRentalPost=true, confidence>=0.5): {listings_feed_visible}")

    print_section("cross-check")
    print(f"unique parsed postId in raw_posts: {len(raw_parsed_post_ids)}")
    print(f"unique postId in raw_posts (all): {len(raw_all_post_ids)}")
    print(f"unique parsed rental postId in raw_posts: {len(raw_parsed_rental_post_ids)}")
    print(f"unique sourcePostId in listings: {len(listings_source_post_ids)}")
    print(f"missing rental postId in listings: {len(missing_rental_post_ids)}")
    print(f"missing rental permalinks in listings: {len(missing_rental_permalinks)}")
    print(f"listings sourcePostId not found in raw_posts: {len(listings_missing_in_raw)}")

    if missing_rental_post_ids:
        print(f"\nSample missing rental postId values (up to {args.sample_size}):")
        for value in missing_rental_post_ids[: args.sample_size]:
            print(f"- {value}")

    if missing_rental_permalinks:
        print(f"\nSample missing rental permalinks (up to {args.sample_size}):")
        for value in missing_rental_permalinks[: args.sample_size]:
            print(f"- {value}")

    if listings_missing_in_raw:
        print(f"\nSample listings sourcePostId missing from raw_posts (up to {args.sample_size}):")
        for value in listings_missing_in_raw[: args.sample_size]:
            print(f"- {value}")

    print_section("quick answer")
    print(f"raw_posts parsed=true: {raw_parsed}")
    print(f"listings total: {listings_total}")
    print(f"listings feed-visible: {listings_feed_visible}")

    print(
        "\nNote: parser logs include both rental and non-rental parses. "
        "Only isRentalPost=true records are written to listings."
    )

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
