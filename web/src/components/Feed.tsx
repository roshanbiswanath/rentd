"use client";

import React, { useMemo, useState } from "react";
import ListingCard from "./ListingCard";
import type { ListingDocument } from "@/lib/listing";
import { listingLocation, toEpoch } from "@/lib/listing";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal, X } from "lucide-react";

const BHK_OPTIONS = ["all", "1", "1.5", "2", "2.5", "3", "4", "5+"] as const;
const BUDGET_OPTIONS = ["all", "under-25", "25-50", "50-plus"] as const;
const FURNISHING_OPTIONS = ["all", "fully_furnished", "semi_furnished", "unfurnished"] as const;
const OWNER_OPTIONS = ["all", "owner", "agent"] as const;
type SortOption = "latest" | "price-asc" | "price-desc" | "confidence";

type Props = {
  initialListings: ListingDocument[];
  totalListings: number;
  pageSize: number;
};

function normalizeBhk(value: string | number | null | undefined): string {
  if (value == null) return "";
  return String(value).toLowerCase().replace(/bhk/g, "").trim();
}

function getRentMin(listing: ListingDocument): number {
  return Number(listing.rentAmount?.min ?? 0) || 0;
}

function inBudget(listing: ListingDocument, budget: (typeof BUDGET_OPTIONS)[number]): boolean {
  if (budget === "all") return true;
  const rent = getRentMin(listing);
  if (!rent) return false;
  if (budget === "under-25") return rent < 25_000;
  if (budget === "25-50") return rent >= 25_000 && rent <= 50_000;
  return rent > 50_000;
}

function formatBhkLabel(option: (typeof BHK_OPTIONS)[number]): string {
  if (option === "all") return "All BHK";
  return `${option} BHK`;
}

function formatFurnishingLabel(option: (typeof FURNISHING_OPTIONS)[number]): string {
  if (option === "all") return "Any furnishing";
  return option.replace(/_/g, " ");
}

function formatOwnerLabel(option: (typeof OWNER_OPTIONS)[number]): string {
  if (option === "all") return "Any source";
  return option === "owner" ? "Owner listed" : "Agent listed";
}

function formatBudgetLabel(option: (typeof BUDGET_OPTIONS)[number]): string {
  if (option === "all") return "Any budget";
  if (option === "under-25") return "Under INR 25k";
  if (option === "25-50") return "INR 25k - 50k";
  return "Above INR 50k";
}

export default function Feed({ initialListings, totalListings, pageSize }: Props) {
  const [loadedListings, setLoadedListings] = useState<ListingDocument[]>(initialListings);
  const [totalAvailable, setTotalAvailable] = useState<number>(totalListings);
  const [filteredTotal, setFilteredTotal] = useState<number>(totalListings);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [bhkFilter, setBhkFilter] = useState<(typeof BHK_OPTIONS)[number]>("all");
  const [budgetFilter, setBudgetFilter] = useState<(typeof BUDGET_OPTIONS)[number]>("all");
  const [furnishingFilter, setFurnishingFilter] =
    useState<(typeof FURNISHING_OPTIONS)[number]>("all");
  const [ownerFilter, setOwnerFilter] = useState<(typeof OWNER_OPTIONS)[number]>("all");
  const [sortBy, setSortBy] = useState<SortOption>("latest");
  const filterRailRef = React.useRef<HTMLDivElement | null>(null);

  // Sort loaded listings
  const filteredListings = useMemo<ListingDocument[]>(() => {
    const sorted = [...loadedListings].sort((a, b) => {
      if (sortBy === "price-asc") return getRentMin(a) - getRentMin(b);
      if (sortBy === "price-desc") return getRentMin(b) - getRentMin(a);
      if (sortBy === "confidence") {
        return Number(b.confidence ?? 0) - Number(a.confidence ?? 0);
      }

      const aTime = toEpoch(a.parsedAt ?? a.postedAt ?? null);
      const bTime = toEpoch(b.parsedAt ?? b.postedAt ?? null);
      return bTime - aTime;
    });

    return sorted;
  }, [loadedListings, sortBy]);

  // When filters or search change, reset to first page and fetch new data
  React.useEffect(() => {
    const fetchFiltered = async () => {
      setIsLoadingMore(true);
      setLoadError("");

      try {
        const query = new URLSearchParams({
          offset: "0",
          limit: String(pageSize),
          search: search.trim(),
          bhk: bhkFilter,
          budget: budgetFilter,
          furnishing: furnishingFilter,
          owner: ownerFilter,
        });

        const response = await fetch(`/api/listings?${query.toString()}`, {
          method: "GET",
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch listings (${response.status})`);
        }

        const payload = (await response.json()) as {
          listings: ListingDocument[];
          total?: number;
        };

        setLoadedListings(payload.listings ?? []);
        if (Number.isFinite(payload.total)) {
          setFilteredTotal(Math.max(0, Number(payload.total)));
          setTotalAvailable(Math.max(0, Number(payload.total)));
        }
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : "Could not load listings.");
        setLoadedListings([]);
      } finally {
        setIsLoadingMore(false);
      }
    };

    fetchFiltered();
  }, [search, bhkFilter, budgetFilter, furnishingFilter, ownerFilter, pageSize]);

  const clearFilters = () => {
    setSearch("");
    setBhkFilter("all");
    setBudgetFilter("all");
    setFurnishingFilter("all");
    setOwnerFilter("all");
    setSortBy("latest");
  };

  const activeFilterCount = [
    bhkFilter !== "all",
    budgetFilter !== "all",
    furnishingFilter !== "all",
    ownerFilter !== "all",
    search.trim().length > 0,
  ].filter(Boolean).length;

  const scrollFilters = (direction: "left" | "right") => {
    const rail = filterRailRef.current;
    if (!rail) return;
    rail.scrollBy({
      left: direction === "left" ? -300 : 300,
      behavior: "smooth",
    });
  };

  React.useEffect(() => {
    const rail = filterRailRef.current;
    if (!rail) return;

    const handleWheel = (event: WheelEvent) => {
      // If primarily scrolling vertically
      if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
        event.preventDefault(); // This requires { passive: false }
        rail.scrollLeft += event.deltaY;
      }
    };

    rail.addEventListener("wheel", handleWheel, { passive: false });
    return () => rail.removeEventListener("wheel", handleWheel);
  }, []);

  const canLoadMore = loadedListings.length < filteredTotal;

  const loadMore = async () => {
    if (!canLoadMore || isLoadingMore) return;
    setIsLoadingMore(true);
    setLoadError("");

    try {
      const query = new URLSearchParams({
        offset: String(loadedListings.length),
        limit: String(pageSize),
        search: search.trim(),
        bhk: bhkFilter,
        budget: budgetFilter,
        furnishing: furnishingFilter,
        owner: ownerFilter,
      });
      const response = await fetch(`/api/listings?${query.toString()}`, {
        method: "GET",
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch listings (${response.status})`);
      }

      const payload = (await response.json()) as {
        listings: ListingDocument[];
        total?: number;
      };

      setLoadedListings((prev) => {
        const seen = new Set(prev.map((item) => item._id));
        const next = [...prev];
        for (const listing of payload.listings ?? []) {
          if (seen.has(listing._id)) continue;
          seen.add(listing._id);
          next.push(listing);
        }
        return next;
      });

      if (Number.isFinite(payload.total)) {
        setFilteredTotal(Math.max(0, Number(payload.total)));
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load more listings.");
    } finally {
      setIsLoadingMore(false);
    }
  };

  return (
    <section
      className="animate-rise-delayed space-y-5"
      style={{ "--delay": "140ms" } as React.CSSProperties}
    >
      <div className="surface sticky top-[5.8rem] z-40 rounded-3xl p-4 sm:p-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative w-full lg:max-w-lg">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <input
                type="text"
                placeholder="Search by locality, title, or keywords"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full rounded-2xl border border-app-line bg-white px-11 py-3 text-sm text-app-ink outline-none transition-all placeholder:text-muted focus:border-app-accent/60 focus:ring-4 focus:ring-app-accent/10"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                Sort
              </label>
              <select
                value={sortBy}
                onChange={(event) =>
                  setSortBy(event.target.value as SortOption)
                }
                className="rounded-xl border border-app-line bg-white px-3 py-2 text-sm font-medium text-app-ink outline-none transition-all focus:border-app-accent/60 focus:ring-4 focus:ring-app-accent/10"
              >
                <option value="latest">Latest first</option>
                <option value="price-asc">Price low to high</option>
                <option value="price-desc">Price high to low</option>
                <option value="confidence">Best confidence</option>
              </select>

              {activeFilterCount > 0 && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1 rounded-xl border border-app-line bg-white px-3 py-2 text-sm font-medium text-app-ink transition-all hover:-translate-y-0.5"
                >
                  <X className="h-3.5 w-3.5" />
                  Clear
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => scrollFilters("left")}
              className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full border border-app-line bg-white text-app-ink transition-all hover:-translate-y-0.5 sm:inline-flex"
              aria-label="Scroll filters left"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            <div
              ref={filterRailRef}
              className="overflow-x-auto pb-1 hide-scrollbar touch-pan-x overscroll-x-contain"
            >
              <div className="flex w-max min-w-full gap-2 pr-2">
              <span className="chip inline-flex shrink-0 items-center gap-2 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Filters
              </span>

              {BHK_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setBhkFilter(option)}
                  className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold transition-all ${
                    bhkFilter === option
                      ? "bg-app-ink text-white"
                      : "chip hover:-translate-y-0.5"
                  }`}
                >
                  {formatBhkLabel(option)}
                </button>
              ))}

              {BUDGET_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setBudgetFilter(option)}
                  className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold transition-all ${
                    budgetFilter === option
                      ? "bg-app-ink text-white"
                      : "chip hover:-translate-y-0.5"
                  }`}
                >
                  {formatBudgetLabel(option)}
                </button>
              ))}

              {FURNISHING_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setFurnishingFilter(option)}
                  className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold capitalize transition-all ${
                    furnishingFilter === option
                      ? "bg-app-ink text-white"
                      : "chip hover:-translate-y-0.5"
                  }`}
                >
                  {formatFurnishingLabel(option)}
                </button>
              ))}

              {OWNER_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setOwnerFilter(option)}
                  className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold transition-all ${
                    ownerFilter === option
                      ? "bg-app-ink text-white"
                      : "chip hover:-translate-y-0.5"
                  }`}
                >
                  {formatOwnerLabel(option)}
                </button>
              ))}
              </div>
            </div>

            <button
              type="button"
              onClick={() => scrollFilters("right")}
              className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full border border-app-line bg-white text-app-ink transition-all hover:-translate-y-0.5 sm:inline-flex"
              aria-label="Scroll filters right"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          Showing <span className="font-semibold text-app-ink">{filteredListings.length}</span> of{" "}
          {filteredTotal} listings
        </p>
        {filteredListings[0] && (
          <p className="text-xs uppercase tracking-[0.12em] text-muted">
            Top area: {listingLocation(filteredListings[0])}
          </p>
        )}
      </div>

      {filteredListings.length > 0 ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {filteredListings.map((listing, index) => (
            <ListingCard key={listing._id} listing={listing} index={index} />
          ))}
        </div>
      ) : (
        <div className="surface rounded-3xl px-6 py-16 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-app-accent-soft text-app-accent">
            <Search className="h-6 w-6" />
          </div>
          <h3 className="display-heading text-2xl font-semibold">No matches yet</h3>
          <p className="mx-auto mt-2 max-w-xl text-muted">
            Try widening your search radius or switching one filter off. The feed updates in real time as
            fresh posts are parsed.
          </p>
          <button
            type="button"
            onClick={clearFilters}
            className="mt-6 rounded-xl bg-app-ink px-5 py-2.5 text-sm font-semibold text-white transition-all hover:-translate-y-0.5"
          >
            Reset all filters
          </button>
        </div>
      )}

      {canLoadMore ? (
        <div className="flex flex-col items-center gap-2 pt-1">
          <button
            type="button"
            onClick={loadMore}
            disabled={isLoadingMore}
            className="rounded-xl border border-app-line bg-white px-5 py-2.5 text-sm font-semibold text-app-ink transition-all hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoadingMore ? "Loading..." : `Load more (${Math.min(pageSize, totalAvailable - loadedListings.length)})`}
          </button>
          {loadError ? <p className="text-xs text-red-600">{loadError}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
