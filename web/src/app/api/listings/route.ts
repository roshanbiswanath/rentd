import { NextRequest, NextResponse } from "next/server";
import clientPromise from "@/lib/mongodb";
import type { ListingDocument, ListingMedia } from "@/lib/listing";

type RawListing = Record<string, unknown> & {
  _id?: unknown;
  media?: unknown;
};

function sanitizeListing(listing: RawListing): ListingDocument {
  const mediaItems = Array.isArray(listing.media)
    ? (listing.media as ListingMedia[])
    : [];
  const validMedia = mediaItems.filter((m) => {
    if (!m?.url) return false;
    const lower = m.url.toLowerCase();
    if (lower.includes(".kf?") || lower.endsWith(".kf")) return false;
    // Profile-pic/thumbnail sizes: _s32x32_, _s32x32&, stp=...s32x32
    if (/_[sp]\d{1,3}x\d{1,3}([_&]|$)/i.test(lower)) return false;
    if (/[&?]stp=[^&]*s\d{1,3}x\d{1,3}/i.test(lower)) return false;
    return true;
  });

  return {
    ...(listing as ListingDocument),
    _id: String(listing._id),
    media: validMedia,
  };
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const offsetRaw = Number(searchParams.get("offset") ?? "0");
  const limitRaw = Number(searchParams.get("limit") ?? "120");
  const searchQuery = searchParams.get("search") ?? "";
  const bhkFilter = searchParams.get("bhk") ?? "";
  const budgetFilter = searchParams.get("budget") ?? "";
  const furnishingFilter = searchParams.get("furnishing") ?? "";
  const ownerFilter = searchParams.get("owner") ?? "";

  const offset = Number.isFinite(offsetRaw) && offsetRaw > 0 ? Math.floor(offsetRaw) : 0;
  const limit = Number.isFinite(limitRaw)
    ? Math.max(1, Math.min(200, Math.floor(limitRaw)))
    : 120;

  const match: Record<string, unknown> = { isRentalPost: true, confidence: { $gte: 0.5 }, isAvailable: { $ne: false } };

  // Apply search filter
  if (searchQuery.trim()) {
    const searchRegex = new RegExp(searchQuery.trim(), "i");
    match.$or = [
      { title: searchRegex },
      { summary: searchRegex },
      { rawContent: searchRegex },
      { "location.locality": searchRegex },
      { "location.area": searchRegex },
      { "location.city": searchRegex },
      { "location.landmark": searchRegex },
    ];
  }

  // Apply BHK filter
  if (bhkFilter && bhkFilter !== "all") {
    match.bhk = bhkFilter;
  }

  // Apply budget filter
  if (budgetFilter && budgetFilter !== "all") {
    if (budgetFilter === "under-25") {
      match["rentAmount.min"] = { $lt: 25_000 };
    } else if (budgetFilter === "25-50") {
      match["rentAmount.min"] = { $gte: 25_000, $lte: 50_000 };
    } else if (budgetFilter === "50-plus") {
      match["rentAmount.min"] = { $gt: 50_000 };
    }
  }

  // Apply furnishing filter
  if (furnishingFilter && furnishingFilter !== "all") {
    match.furnishing = furnishingFilter;
  }

  // Apply owner filter
  if (ownerFilter && ownerFilter !== "all") {
    if (ownerFilter === "owner") {
      match.isAgent = false;
    } else if (ownerFilter === "agent") {
      match.isAgent = true;
    }
  }

  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB || "facebook_scraper");
  const collection = db.collection("listings");

  const [rows, total] = await Promise.all([
    collection.find(match).sort({ parsedAt: -1 }).skip(offset).limit(limit).toArray(),
    collection.countDocuments(match),
  ]);

  const listings = rows.map(sanitizeListing);
  return NextResponse.json({ listings, total, offset, limit });
}
