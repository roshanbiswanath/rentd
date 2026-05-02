import clientPromise from "@/lib/mongodb";
import Feed from "@/components/Feed";
import type { ListingDocument, ListingMedia } from "@/lib/listing";
import Link from "next/link";
import {
  Building2,
  CircleDollarSign,
  Sparkles,
  TrendingUp,
} from "lucide-react";
export const dynamic = "force-dynamic";

export default async function Home() {
  const PAGE_SIZE = 120;
  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB || "facebook_scraper");
  const collection = db.collection("listings");
  const listingMatch = { isRentalPost: true, confidence: { $gte: 0.5 }, isAvailable: { $ne: false } };

  // Fetch first page and paginate additional records from client.
  const listings = await collection
    .find(listingMatch)
    .sort({ parsedAt: -1 })
    .limit(PAGE_SIZE)
    .toArray();

  const totalListings = await collection.countDocuments(listingMatch);

  const activeThisWeekResult = await collection.aggregate<{ count: number }>([
    { $match: listingMatch },
    {
      $match: {
        $expr: {
          $gte: [
            {
              $dateFromString: {
                dateString: "$postedAt",
                onError: null,
                onNull: null,
              },
            },
            {
              $dateSubtract: {
                startDate: "$$NOW",
                unit: "day",
                amount: 7,
              },
            },
          ],
        },
      },
    },
    { $count: "count" },
  ]).toArray();
  const activeListingsThisWeek = activeThisWeekResult[0]?.count ?? 0;

  const serializedListings = listings.map((listing) => {
    // Filter out profile pics and .kf animations from existing DB records
    const validMedia = listing.media?.filter((m: ListingMedia) => {
      if (!m.url) return false;
      const lower = m.url.toLowerCase();
      if (lower.includes(".kf?") || lower.endsWith(".kf")) return false;
      // Profile-pic/thumbnail sizes: _s32x32_, _s32x32&, stp=...s32x32
      if (/_[sp]\d{1,3}x\d{1,3}([_&]|$)/i.test(lower)) return false;
      if (/[&?]stp=[^&]*s\d{1,3}x\d{1,3}/i.test(lower)) return false;
      return true;
    }) || [];

    return {
      ...listing,
      _id: String(listing._id),
      media: validMedia,
    };
  }) as ListingDocument[];

  const rents = serializedListings
    .map((item) => item.rentAmount?.min)
    .filter((value): value is number => Number.isFinite(value));
  const avgRent = rents.length
    ? Math.round(rents.reduce((sum, value) => sum + value, 0) / rents.length)
    : 0;
  const ownerCount = serializedListings.filter((item) => item.isAgent === false).length;
  const ownerShare = serializedListings.length
    ? Math.round((ownerCount / serializedListings.length) * 100)
    : 0;

  return (
    <div className="min-h-screen pb-14">
      <header className="sticky top-0 z-50 border-b border-app-line/90 bg-app-surface/85 backdrop-blur-xl">
        <div className="app-container flex h-20 items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-app-accent text-white shadow-sm">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <p className="display-heading text-xl font-semibold leading-none">rentd</p>
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted">curated rentals</p>
            </div>
          </Link>

          <nav className="hidden items-center gap-6 text-sm font-medium text-muted md:flex">
            <Link href="/" className="text-app-ink">Listings</Link>
            <Link href="/neighborhoods" className="transition-colors hover:text-app-ink">Neighborhoods</Link>
            <Link href="/insights" className="transition-colors hover:text-app-ink">Insights</Link>
            <Link href="/contact" className="transition-colors hover:text-app-ink">Contact</Link>
          </nav>
        </div>
      </header>

      <main className="app-container space-y-8 pt-8 sm:pt-10">
        <section className="surface animate-rise relative overflow-hidden rounded-3xl p-6 sm:p-10">
          <div className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-app-accent-soft blur-2xl" />
          <div className="pointer-events-none absolute bottom-0 right-0 h-40 w-40 rounded-full bg-[#d6e7ff] blur-2xl" />

          <div className="relative z-10 max-w-3xl">
            <div className="chip mb-5 inline-flex items-center gap-2 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-app-accent">
              <Sparkles className="h-3.5 w-3.5" />
              Smart Rental Discovery
            </div>
            <h1 className="display-heading text-balance text-3xl font-semibold leading-[1.08] sm:text-5xl">
              Find quality rentals before they hit crowded property portals.
            </h1>
            <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
              Rentd converts noisy social posts into a refined discovery experience with
              structured filters, sharper context, and better signals for decision-making.
            </p>
          </div>

          <div className="relative z-10 mt-8 grid gap-3 sm:grid-cols-3">
            <article className="rounded-2xl border border-app-line/85 bg-white/65 px-4 py-3 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Active listings (7d)</p>
              <p className="mt-1 text-2xl font-semibold text-app-ink">{activeListingsThisWeek}</p>
            </article>
            <article className="rounded-2xl border border-app-line/85 bg-white/65 px-4 py-3 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Average monthly rent</p>
              <p className="mt-1 flex items-center gap-2 text-2xl font-semibold text-app-ink">
                <CircleDollarSign className="h-5 w-5 text-app-accent" />
                {avgRent ? `INR ${new Intl.NumberFormat("en-IN").format(avgRent)}` : "N/A"}
              </p>
            </article>
            <article className="rounded-2xl border border-app-line/85 bg-white/65 px-4 py-3 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Owner-led inventory</p>
              <p className="mt-1 flex items-center gap-2 text-2xl font-semibold text-app-ink">
                <TrendingUp className="h-5 w-5 text-app-accent" />
                {ownerShare}%
              </p>
            </article>
          </div>
        </section>

        <Feed initialListings={serializedListings} totalListings={totalListings} pageSize={PAGE_SIZE} />
      </main>
    </div>
  );
}
