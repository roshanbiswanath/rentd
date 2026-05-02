/* eslint-disable @next/next/no-img-element */

import React from "react";
import Link from "next/link";
import type { ListingDocument } from "@/lib/listing";
import {
  compactInr,
  listingFurnishing,
  listingLocation,
  listingPrimaryVisual,
  listingSummary,
  listingTitle,
} from "@/lib/listing";
import { ArrowUpRight, BadgeCheck, BedDouble, Building2, Ruler } from "lucide-react";

type ListingCardProps = {
  listing: ListingDocument;
  index?: number;
};

export default function ListingCard({ listing, index = 0 }: ListingCardProps) {
  const title = listingTitle(listing);
  const location = listingLocation(listing);
  const summary = listingSummary(listing);
  const primaryVisual = listingPrimaryVisual(listing);
  const image = primaryVisual?.url ?? "";
  const isVideo = primaryVisual?.type === "video";
  const rent = compactInr(listing.rentAmount?.min ?? null);
  const confidence = Math.round(Number(listing.confidence ?? 0) * 100);
  const bhk = listing.bhk ? `${String(listing.bhk).replace(/\s*bhk\s*/i, "")} BHK` : "BHK not specified";

  return (
    <article
      className="animate-rise-delayed"
      style={{ "--delay": `${Math.min(index, 10) * 55}ms` } as React.CSSProperties}
    >
      <Link
        href={`/listing/${listing._id}`}
        className="surface group flex h-full flex-col overflow-hidden rounded-3xl transition-all duration-300 hover:-translate-y-1 hover:shadow-xl"
      >
        <div className="relative aspect-[16/11] w-full overflow-hidden bg-[#dce6dc]">
          {image ? (
            isVideo ? (
              <video
                src={image}
                className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                muted
                loop
                autoPlay
                playsInline
                preload="metadata"
              />
            ) : (
              <img
                src={image}
                alt={title}
                className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                loading="lazy"
              />
            )
          ) : (
            <img
              src="/placeholder.png"
              alt="Premium listing placeholder"
              className="h-full w-full object-cover grayscale-[0.2] opacity-80"
            />
          )}

          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/45 to-transparent" />

          <div className="absolute left-3 top-3 flex flex-wrap gap-2">
            {listing.isAgent === false && (
              <span className="inline-flex items-center gap-1 rounded-full bg-white/88 px-2.5 py-1 text-[11px] font-semibold text-app-ink backdrop-blur-sm">
                <BadgeCheck className="h-3.5 w-3.5 text-app-accent" />
                Owner
              </span>
            )}
            {confidence > 0 && (
              <span className="rounded-full bg-app-ink/80 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
                {confidence}% confidence
              </span>
            )}
            {isVideo && (
              <span className="rounded-full bg-app-accent/85 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
                Video
              </span>
            )}
          </div>

          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.14em] text-white/80">Rent / month</p>
              <p className="display-heading text-xl font-semibold text-white">{rent}</p>
            </div>
            <span className="rounded-full border border-white/30 bg-white/20 p-2 text-white backdrop-blur-sm">
              <ArrowUpRight className="h-4 w-4" />
            </span>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3 p-4">
          <div>
            <h3 className="display-heading line-clamp-1 text-xl font-semibold text-app-ink">{title}</h3>
            <p className="mt-1 line-clamp-1 text-sm text-muted">{location}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="chip inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium text-muted">
              <BedDouble className="h-3.5 w-3.5" />
              {bhk}
            </span>
            <span className="chip inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium capitalize text-muted">
              <Building2 className="h-3.5 w-3.5" />
              {listingFurnishing(listing)}
            </span>
            {listing.sqft ? (
              <span className="chip inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium text-muted">
                <Ruler className="h-3.5 w-3.5" />
                {listing.sqft} sqft
              </span>
            ) : null}
          </div>

          <p className="line-clamp-2 text-sm text-muted">{summary}</p>
        </div>
      </Link>
    </article>
  );
}
