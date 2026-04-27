import Link from "next/link";
import { ArrowLeft, Compass, MapPinned } from "lucide-react";

export const metadata = {
  title: "Neighborhoods | Rentd",
  description: "Neighborhood intelligence is coming soon.",
};

export default function NeighborhoodsPage() {
  return (
    <div className="min-h-screen pb-16">
      <header className="sticky top-0 z-50 border-b border-app-line/90 bg-app-surface/85 backdrop-blur-xl">
        <div className="app-container flex h-20 items-center justify-between">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-muted transition-colors hover:text-app-ink">
            <ArrowLeft className="h-4 w-4" />
            Back to listings
          </Link>
          <span className="chip rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-app-accent">
            Placeholder
          </span>
        </div>
      </header>

      <main className="app-container pt-10">
        <section className="surface animate-rise relative overflow-hidden rounded-3xl p-7 sm:p-10">
          <div className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full bg-app-accent-soft blur-2xl" />

          <div className="relative z-10 max-w-2xl">
            <div className="chip inline-flex items-center gap-2 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-app-accent">
              <Compass className="h-3.5 w-3.5" />
              Neighborhoods
            </div>
            <h1 className="display-heading mt-5 text-4xl font-semibold leading-tight text-app-ink">
              Locality intelligence is on the way.
            </h1>
            <p className="mt-3 text-base text-muted sm:text-lg">
              This page will soon show rent trends, supply pressure, and live heatmaps across key micro-markets.
            </p>
          </div>

          <div className="relative z-10 mt-8 grid gap-3 sm:grid-cols-2">
            <article className="rounded-2xl border border-app-line/85 bg-white/65 px-4 py-3 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Planned module</p>
              <p className="mt-1 inline-flex items-center gap-2 text-lg font-semibold text-app-ink">
                <MapPinned className="h-4 w-4 text-app-accent" />
                Area scorecards
              </p>
            </article>
            <article className="rounded-2xl border border-app-line/85 bg-white/65 px-4 py-3 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Planned module</p>
              <p className="mt-1 text-lg font-semibold text-app-ink">Transit and commute overlays</p>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
}
