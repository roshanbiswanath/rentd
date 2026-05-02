import Link from "next/link";
import { ArrowLeft, ArrowUpRight, Mail, MessageSquare, MessageSquareWarning } from "lucide-react";

export const metadata = {
  title: "Contact | Rentd",
  description: "Send feedback, complaints, or feature requests for Rentd.",
};

function buildMailto(subject: string, body: string, fallbackEmail: string | null): string {
  if (!fallbackEmail) return "";
  const params = new URLSearchParams({ subject, body });
  return `mailto:${fallbackEmail}?${params.toString()}`;
}

export default function ContactPage() {
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || process.env.CONTACT_EMAIL || "";
  const contactWhatsApp =
    process.env.NEXT_PUBLIC_CONTACT_WHATSAPP || process.env.CONTACT_WHATSAPP || "";

  return (
    <div className="min-h-screen pb-16">
      <header className="sticky top-0 z-50 border-b border-app-line/90 bg-app-surface/85 backdrop-blur-xl">
        <div className="app-container flex h-20 items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted transition-colors hover:text-app-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to listings
          </Link>
          <span className="chip rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-app-accent">
            Contact
          </span>
        </div>
      </header>

      <main className="app-container pt-10">
        <section className="surface animate-rise relative overflow-hidden rounded-3xl p-7 sm:p-10">
          <div className="pointer-events-none absolute -right-12 -top-20 h-56 w-56 rounded-full bg-app-accent-soft blur-2xl" />
          <div className="pointer-events-none absolute bottom-0 left-0 h-44 w-44 rounded-full bg-[#d6e7ff] blur-2xl" />

          <div className="relative z-10 max-w-2xl space-y-4">
            <div className="chip inline-flex items-center gap-2 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-app-accent">
              <Mail className="h-3.5 w-3.5" />
              Feedback & contact
            </div>
            <h1 className="display-heading text-4xl font-semibold leading-tight text-app-ink sm:text-5xl">
              Report a problem, suggest a feature, or contact me directly.
            </h1>
            <p className="max-w-2xl text-base text-muted sm:text-lg">
              Use this page for complaints, content corrections, feature ideas, or general contact.
              Messages are easier to track here than through listing pages.
            </p>
          </div>

          <div className="relative z-10 mt-8 grid gap-3 lg:grid-cols-3">
            <article className="rounded-2xl border border-app-line/85 bg-white/65 p-4 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Complaint</p>
              <p className="mt-2 text-sm text-app-ink">
                Report duplicate listings, misleading posts, broken links, or content that should be hidden.
              </p>
              <a
                href={buildMailto(
                  "Rentd complaint",
                  "Hi,\n\nI found a listing issue that should be reviewed.\n\nListing link: \nReason: \n\nThanks.",
                  contactEmail || null,
                ) || "#"}
                className={`mt-4 inline-flex items-center gap-2 text-sm font-semibold transition-colors ${
                  contactEmail ? "text-app-ink hover:text-app-accent" : "pointer-events-none text-muted"
                }`}
              >
                Email complaint
                <ArrowUpRight className="h-4 w-4" />
              </a>
            </article>

            <article className="rounded-2xl border border-app-line/85 bg-white/65 p-4 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Feature request</p>
              <p className="mt-2 text-sm text-app-ink">
                Request filters, alerts, neighborhood views, or anything that improves the product.
              </p>
              <a
                href={buildMailto(
                  "Rentd feature request",
                  "Hi,\n\nI would like to suggest a feature for Rentd.\n\nFeature idea: \nWhy it would help: \n\nThanks.",
                  contactEmail || null,
                ) || "#"}
                className={`mt-4 inline-flex items-center gap-2 text-sm font-semibold transition-colors ${
                  contactEmail ? "text-app-ink hover:text-app-accent" : "pointer-events-none text-muted"
                }`}
              >
                Suggest a feature
                <ArrowUpRight className="h-4 w-4" />
              </a>
            </article>

            <article className="rounded-2xl border border-app-line/85 bg-white/65 p-4 shadow-[0_4px_14px_rgba(34,44,38,0.04)]">
              <p className="text-xs uppercase tracking-[0.14em] text-muted">Direct contact</p>
              <p className="mt-2 text-sm text-app-ink">
                Reach out by email or WhatsApp if you want a faster reply.
              </p>
              <div className="mt-4 flex flex-col gap-2">
                <a
                  href={contactEmail ? `mailto:${contactEmail}` : "#"}
                  className={`inline-flex items-center gap-2 text-sm font-semibold transition-colors ${
                    contactEmail ? "text-app-ink hover:text-app-accent" : "pointer-events-none text-muted"
                  }`}
                >
                  <MessageSquareWarning className="h-4 w-4" />
                  {contactEmail || "Set CONTACT_EMAIL"}
                </a>
                <a
                  href={contactWhatsApp ? `https://wa.me/${contactWhatsApp.replace(/[^\d]/g, "")}` : "#"}
                  target="_blank"
                  rel="noreferrer"
                  className={`inline-flex items-center gap-2 text-sm font-semibold transition-colors ${
                    contactWhatsApp ? "text-app-ink hover:text-app-accent" : "pointer-events-none text-muted"
                  }`}
                >
                  <MessageSquare className="h-4 w-4" />
                  {contactWhatsApp || "Set CONTACT_WHATSAPP"}
                </a>
              </div>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
}
