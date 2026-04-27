/* eslint-disable @next/next/no-img-element */

import clientPromise from "@/lib/mongodb";
import type { ListingDocument } from "@/lib/listing";
import {
  formatInr,
  listingFurnishing,
  listingLocation,
  listingRenderableMedia,
  listingSummary,
  listingTitle,
} from "@/lib/listing";
import { ObjectId } from "mongodb";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  BadgeCheck,
  BedDouble,
  Building2,
  CalendarDays,
  CircleDollarSign,
  MapPin,
  Phone,
  Ruler,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

type PageProps = {
  params: Promise<{ id: string }>;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function uniqueNonEmpty(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.map((entry) => String(entry ?? "").trim()).filter(Boolean))];
}

export default async function PropertyDetails({ params }: PageProps) {
  let objectId: ObjectId;

  try {
    const { id } = await params;
    objectId = new ObjectId(id);
  } catch {
    return notFound();
  }

  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB || "facebook_scraper");
  const rawListing = await db.collection("listings").findOne({ _id: objectId });

  if (!rawListing) return notFound();

  const listing = {
    ...rawListing,
    _id: String(rawListing._id),
  } as ListingDocument;

  const title = listingTitle(listing);
  const summary = listingSummary(listing);
  const location = listingLocation(listing);
  const mediaItems = listingRenderableMedia(listing);
  const coverMedia = mediaItems[0] ?? null;
  const gallery = mediaItems;
  const amenities = uniqueNonEmpty([...(listing.amenities ?? []), ...(listing.other_amenities ?? [])]);
  const rentMin = listing.rentAmount?.min ?? null;
  const rentMax = listing.rentAmount?.max ?? null;
  const confidence = Math.round(Number(listing.confidence ?? 0) * 100);
  const phones = uniqueNonEmpty(listing.contactInfo?.phone ?? []);
  const whatsapps = uniqueNonEmpty(listing.contactInfo?.whatsapp ?? []);
  const contactName = String(listing.contactInfo?.name ?? "").trim();

  return (
    <div className="min-h-screen pb-24">
      <header className="sticky top-0 z-50 border-b border-app-line/90 bg-app-surface/85 backdrop-blur-xl">
        <div className="app-container flex h-20 items-center justify-between">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-muted transition-colors hover:text-app-ink">
            <ArrowLeft className="h-4 w-4" />
            Back to listings
          </Link>
          <a
            href={listing.permalink || "#"}
            target="_blank"
            rel="noreferrer"
            className="chip inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-app-ink transition-all hover:-translate-y-0.5"
          >
            View source post
            <ArrowUpRight className="h-4 w-4" />
          </a>
        </div>
      </header>

      <main className="app-container space-y-6 pt-7 sm:pt-10">
        <section className="surface animate-rise overflow-hidden rounded-3xl">
          <div className="grid gap-0 lg:grid-cols-5">
            <div className="relative min-h-[320px] lg:col-span-3 lg:min-h-[460px]">
              {coverMedia ? (
                coverMedia.type === "video" ? (
                  <video
                    src={coverMedia.url}
                    className="h-full w-full object-cover"
                    controls
                    playsInline
                    preload="metadata"
                  />
                ) : (
                  <img
                    src={coverMedia.url}
                    alt={title}
                    className="h-full w-full object-cover"
                  />
                )
              ) : (
                <div className="flex h-full min-h-[320px] items-center justify-center bg-gradient-to-br from-[#dce7de] to-[#c8d5cc] text-muted">
                  Image not available
                </div>
              )}

              <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-black/45 to-transparent" />
              <div className="absolute bottom-5 left-5">
                <p className="text-xs uppercase tracking-[0.14em] text-white/80">Monthly rent</p>
                <p className="display-heading text-3xl font-semibold text-white">{formatInr(rentMin)}</p>
              </div>
            </div>

            <div className="flex flex-col gap-5 p-5 sm:p-7 lg:col-span-2">
              <div>
                <div className="chip mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.13em] text-app-accent">
                  <Sparkles className="h-3.5 w-3.5" />
                  Curated listing
                </div>
                <h1 className="display-heading text-balance text-3xl font-semibold leading-tight">{title}</h1>
                <p className="mt-2 inline-flex items-center gap-2 text-sm text-muted">
                  <MapPin className="h-4 w-4" />
                  {location}
                </p>
              </div>

              <p className="text-sm leading-relaxed text-muted">{summary}</p>

              <div className="grid grid-cols-2 gap-2">
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Posted</p>
                  <p className="mt-1 text-sm font-semibold text-app-ink">{formatDate(listing.postedAt)}</p>
                </div>
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Confidence</p>
                  <p className="mt-1 text-sm font-semibold text-app-ink">{confidence}%</p>
                </div>
              </div>

              <a
                href={listing.permalink || "#"}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-app-ink px-4 py-3 text-sm font-semibold text-white transition-all hover:-translate-y-0.5"
              >
                Open original listing
                <ArrowUpRight className="h-4 w-4" />
              </a>
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-6">
            {gallery.length > 1 && (
              <article className="surface animate-rise-delayed rounded-3xl p-4" style={{ "--delay": "70ms" } as React.CSSProperties}>
                <h2 className="display-heading text-xl font-semibold">Gallery</h2>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {gallery.slice(1, 7).map((item) => (
                    <div key={`${item.type}-${item.url}`} className="overflow-hidden rounded-2xl bg-[#d4ddd5]">
                      {item.type === "video" ? (
                        <video
                          src={item.url}
                          className="aspect-[4/3] w-full object-cover"
                          controls
                          playsInline
                          preload="metadata"
                        />
                      ) : (
                        <img src={item.url} alt={title} className="aspect-[4/3] w-full object-cover" />
                      )}
                    </div>
                  ))}
                </div>
              </article>
            )}

            <article className="surface animate-rise-delayed rounded-3xl p-5 sm:p-6" style={{ "--delay": "120ms" } as React.CSSProperties}>
              <h2 className="display-heading text-2xl font-semibold">Property profile</h2>
              <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Type</p>
                  <p className="mt-1 text-sm font-semibold capitalize text-app-ink">
                    {String(listing.propertyType ?? "Property")}
                  </p>
                </div>
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Configuration</p>
                  <p className="mt-1 text-sm font-semibold text-app-ink">
                    {listing.bhk ? `${String(listing.bhk)} BHK` : "Not specified"}
                  </p>
                </div>
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Furnishing</p>
                  <p className="mt-1 text-sm font-semibold capitalize text-app-ink">
                    {listingFurnishing(listing)}
                  </p>
                </div>
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Area</p>
                  <p className="mt-1 text-sm font-semibold text-app-ink">
                    {listing.sqft ? `${listing.sqft} sqft` : "Unknown"}
                  </p>
                </div>
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Floor</p>
                  <p className="mt-1 text-sm font-semibold text-app-ink">
                    {listing.floor || "Unknown"}
                  </p>
                </div>
                <div className="chip rounded-2xl px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.13em] text-muted">Source</p>
                  <p className="mt-1 text-sm font-semibold text-app-ink">
                    {listing.author || "Community listing"}
                  </p>
                </div>
              </div>
            </article>

            {amenities.length > 0 && (
              <article className="surface animate-rise-delayed rounded-3xl p-5 sm:p-6" style={{ "--delay": "180ms" } as React.CSSProperties}>
                <h2 className="display-heading text-2xl font-semibold">Amenities & highlights</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                  {amenities.map((amenity) => (
                    <span
                      key={amenity}
                      className="chip rounded-full px-3 py-1.5 text-sm font-medium capitalize text-app-ink"
                    >
                      {amenity.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </article>
            )}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            <article className="surface animate-rise-delayed rounded-3xl p-5" style={{ "--delay": "90ms" } as React.CSSProperties}>
              <h2 className="display-heading text-xl font-semibold">Rental economics</h2>

              <div className="mt-4 space-y-2">
                <div className="chip flex items-center justify-between rounded-2xl px-3 py-2">
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted">
                    <CircleDollarSign className="h-4 w-4" />
                    Rent range
                  </span>
                  <span className="text-sm font-semibold text-app-ink">
                    {rentMin && rentMax && rentMax !== rentMin
                      ? `${formatInr(rentMin)} - ${formatInr(rentMax)}`
                      : formatInr(rentMin)}
                  </span>
                </div>
                <div className="chip flex items-center justify-between rounded-2xl px-3 py-2">
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted">
                    <CalendarDays className="h-4 w-4" />
                    Deposit
                  </span>
                  <span className="text-sm font-semibold text-app-ink">
                    {listing.deposit?.amount ? formatInr(listing.deposit.amount) : "Not listed"}
                  </span>
                </div>
                <div className="chip flex items-center justify-between rounded-2xl px-3 py-2">
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted">
                    <ShieldCheck className="h-4 w-4" />
                    Listing type
                  </span>
                  <span className="text-sm font-semibold text-app-ink">
                    {listing.isAgent ? "Agent" : "Owner"}
                  </span>
                </div>
              </div>
            </article>

            <article className="surface animate-rise-delayed rounded-3xl p-5" style={{ "--delay": "130ms" } as React.CSSProperties}>
              <h2 className="display-heading text-xl font-semibold">Contact</h2>

              <div className="mt-4 space-y-2">
                {contactName ? (
                  <p className="chip inline-flex rounded-full px-3 py-1 text-sm font-medium text-app-ink">
                    {contactName}
                  </p>
                ) : null}

                {phones.length > 0 ? (
                  phones.map((phone) => (
                    <a
                      key={phone}
                      href={`tel:${phone}`}
                      className="chip flex items-center justify-between rounded-2xl px-3 py-2 text-sm font-medium text-app-ink transition-all hover:-translate-y-0.5"
                    >
                      <span className="inline-flex items-center gap-1.5">
                        <Phone className="h-4 w-4" />
                        {phone}
                      </span>
                      <ArrowUpRight className="h-4 w-4" />
                    </a>
                  ))
                ) : (
                  <p className="text-sm text-muted">Phone number not available.</p>
                )}

                {whatsapps.length > 0 ? (
                  whatsapps.map((number) => (
                    <a
                      key={number}
                      href={`https://wa.me/${number.replace(/[^\d]/g, "")}`}
                      target="_blank"
                      rel="noreferrer"
                      className="chip flex items-center justify-between rounded-2xl px-3 py-2 text-sm font-medium text-app-ink transition-all hover:-translate-y-0.5"
                    >
                      <span className="inline-flex items-center gap-1.5">
                        <BadgeCheck className="h-4 w-4" />
                        WhatsApp {number}
                      </span>
                      <ArrowUpRight className="h-4 w-4" />
                    </a>
                  ))
                ) : null}
              </div>
            </article>

            <article className="surface animate-rise-delayed rounded-3xl p-5" style={{ "--delay": "170ms" } as React.CSSProperties}>
              <h2 className="display-heading text-xl font-semibold">Quick facts</h2>
              <ul className="mt-4 space-y-2 text-sm text-muted">
                <li className="inline-flex items-center gap-2">
                  <BedDouble className="h-4 w-4 text-app-accent" />
                  {listing.bhk ? `${String(listing.bhk)} BHK configuration` : "BHK not specified"}
                </li>
                <li className="inline-flex items-center gap-2">
                  <Ruler className="h-4 w-4 text-app-accent" />
                  {listing.sqft ? `${listing.sqft} sqft built-up area` : "Area details unavailable"}
                </li>
                <li className="inline-flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-app-accent" />
                  {listingFurnishing(listing)}
                </li>
              </ul>
            </article>
          </aside>
        </section>
      </main>
    </div>
  );
}
