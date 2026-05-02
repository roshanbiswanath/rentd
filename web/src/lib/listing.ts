export type ListingMedia = {
  type?: string | null;
  url?: string | null;
  width?: number | null;
  height?: number | null;
};

export type ListingVisual = {
  type: "image" | "video";
  url: string;
  width: number | null;
  height: number | null;
};

export type ListingLocation = {
  locality?: string | null;
  area?: string | null;
  city?: string | null;
  landmark?: string | null;
};

export type ListingContactInfo = {
  phone?: string[];
  whatsapp?: string[];
  name?: string | null;
};

export type ListingDocument = {
  _id: string;
  title?: string | null;
  summary?: string | null;
  rawContent?: string | null;
  propertyType?: string | null;
  bhk?: string | number | null;
  rentAmount?: {
    min?: number | null;
    max?: number | null;
    currency?: string | null;
  } | null;
  deposit?: {
    amount?: number | null;
    months?: number | null;
  } | null;
  sqft?: number | null;
  floor?: string | null;
  location?: ListingLocation | null;
  furnishing?: string | null;
  amenities?: string[];
  other_amenities?: string[];
  contactInfo?: ListingContactInfo | null;
  isAgent?: boolean | null;
  media?: ListingMedia[];
  isAvailable?: boolean | null;
  supersededBy?: string | null;
  confidence?: number | null;
  postedAt?: string | null;
  scrapedAt?: string | null;
  parsedAt?: string | null;
  permalink?: string | null;
  author?: string | null;
};

function cleanText(value: string | null | undefined): string {
  return String(value ?? "").trim();
}

function classifyVisual(item: ListingMedia | null | undefined): ListingVisual | null {
  const url = cleanText(item?.url);
  if (!url || !/^https?:\/\//i.test(url)) return null;

  const lower = url.toLowerCase();
  if (
    /facebook\.com\/photo(\.php|\/)|facebook\.com\/.*\/photos\//i.test(lower) ||
    /\/groups\/\d+\/posts\/|\/permalink\/\d+|story_fbid=|multi_permalinks=/i.test(lower) ||
    /\.kf(\?|$)/i.test(lower) ||
    // Profile-pic/thumbnail size patterns: _s32x32_, _s32x32&, stp=...s32x32, etc.
    /_[sp]\d{1,3}x\d{1,3}([_&]|$)/i.test(lower) ||
    /[&?]stp=[^&]*s\d{1,3}x\d{1,3}/i.test(lower)
  ) {
    return null;
  }

  const declared = cleanText(item?.type).toLowerCase();
  const hasDirectVideoSignal = /\.(mp4|m3u8)(\?|$)/i.test(lower) || /\/videos?\//i.test(lower);
  const isVideo =
    hasDirectVideoSignal ||
    (declared === "video" && (/fbcdn\.net/i.test(lower) || hasDirectVideoSignal));
  if (isVideo) {
    return {
      type: "video",
      url,
      width: Number.isFinite(item?.width) ? Number(item?.width) : null,
      height: Number.isFinite(item?.height) ? Number(item?.height) : null,
    };
  }

  const isImage =
    /fbcdn\.net/i.test(lower) ||
    /\.(jpe?g|png|webp|gif|bmp)(\?|$)/i.test(lower);
  if (!isImage) return null;

  return {
    type: "image",
    url,
    width: Number.isFinite(item?.width) ? Number(item?.width) : null,
    height: Number.isFinite(item?.height) ? Number(item?.height) : null,
  };
}

export function formatInr(value: number | null | undefined): string {
  if (!Number.isFinite(value)) return "Price on request";
  return `INR ${new Intl.NumberFormat("en-IN").format(Number(value))}`;
}

export function compactInr(value: number | null | undefined): string {
  if (!Number.isFinite(value)) return "N/A";
  return `INR ${new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value))}`;
}

export function listingLocation(listing: ListingDocument): string {
  const location = listing.location ?? {};
  const parts = [location.locality, location.area, location.city]
    .map((part) => cleanText(part))
    .filter(Boolean);
  return parts.join(", ") || "Location undisclosed";
}

export function listingTitle(listing: ListingDocument): string {
  const bhk = cleanText(String(listing.bhk ?? "")).replace(/\s*bhk\s*/i, "");
  const locality = cleanText(listing.location?.locality) || cleanText(listing.location?.area);

  if (bhk && locality) {
    return `${bhk} BHK in ${locality}`;
  }

  return cleanText(listing.title) || "Premium rental listing";
}

export function listingSummary(listing: ListingDocument): string {
  const summary = cleanText(listing.summary);
  if (summary) return summary;

  const fallback = cleanText(listing.rawContent);
  if (!fallback) return "No summary available yet for this listing.";

  return fallback.length > 180 ? `${fallback.slice(0, 180).trim()}...` : fallback;
}

export function listingFurnishing(listing: ListingDocument): string {
  const furnishing = cleanText(listing.furnishing);
  if (!furnishing) return "Furnishing not specified";
  return furnishing.replace(/_/g, " ");
}

export function listingPrimaryMedia(listing: ListingDocument): string {
  return listingPrimaryVisual(listing)?.url ?? "";
}

export function listingPrimaryVisual(listing: ListingDocument): ListingVisual | null {
  const visuals = listingRenderableMedia(listing);
  return visuals.length > 0 ? visuals[0] : null;
}

export function listingRenderableMedia(listing: ListingDocument): ListingVisual[] {
  const media = listing.media ?? [];
  const visuals: ListingVisual[] = [];
  const seen = new Set<string>();

  for (const item of media) {
    const visual = classifyVisual(item);
    if (!visual) continue;

    const dedupeKey = visual.url.replace(/[?#].*$/, "");
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    visuals.push(visual);
  }

  return visuals;
}

export function toEpoch(value: string | null | undefined): number {
  if (!value) return 0;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? 0 : ms;
}

export function withStringId<T extends { _id: unknown }>(doc: T): Omit<T, "_id"> & { _id: string } {
  return {
    ...doc,
    _id: String(doc._id),
  };
}
