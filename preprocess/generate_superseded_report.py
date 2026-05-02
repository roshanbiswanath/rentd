r"""
Generate a report of all superseded listings from the database.

This queries the current database state without recomputing hashes.
Run this after detect_historical_reposts.py or whenever you want a current report.

Usage:
  .venv\Scripts\python generate_superseded_report.py --report-file ../reports/superseded_report.json

Options:
  --report-file: JSON file for results (defaults to ../reports/superseded_report.json)
"""

import argparse
import json
import os
from pymongo import MongoClient
from bson import ObjectId

import config


def main():
    ap = argparse.ArgumentParser(description="Generate report of superseded listings")
    ap.add_argument("--mongo-uri", default=config.MONGO_URI)
    ap.add_argument("--mongo-db", default=config.MONGO_DB)
    ap.add_argument("--listings-collection", default=config.LISTINGS_COLLECTION)
    ap.add_argument("--report-file", default="../reports/superseded_report.json")
    args = ap.parse_args()

    client = MongoClient(args.mongo_uri)
    db = client[args.mongo_db]
    listings_coll = db[args.listings_collection]

    print("Querying database for superseded listings...")

    # Count total listings
    total_listings = listings_coll.count_documents({})

    # Count superseded listings
    superseded = list(
        listings_coll.find(
            {"isAvailable": False, "supersededBy": {"$exists": True, "$ne": None}},
            {"_id": 1, "title": 1, "supersededBy": 1, "postedAt": 1},
        )
    )
    superseded_count = len(superseded)

    print(f"Total listings: {total_listings}")
    print(f"Superseded listings: {superseded_count}")

    # Build report
    report = {
        "summary": {
            "total_listings": total_listings,
            "superseded_count": superseded_count,
        },
        "items": [
            {
                "older_id": str(item["_id"]),
                "newer_id": str(item.get("supersededBy", "")),
                "title": str(item.get("title", "")),
                "posted_date": str(item.get("postedAt", "")),
            }
            for item in superseded
        ],
    }

    # Ensure report directory exists
    report_dir = os.path.dirname(args.report_file)
    if report_dir and not os.path.exists(report_dir):
        os.makedirs(report_dir, exist_ok=True)

    # Write report
    with open(args.report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report written to {args.report_file}")


if __name__ == "__main__":
    main()
