import React from "react";
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="page-shell space-y-6">
      <section className="surface-card overflow-hidden">
        <div className="bg-gradient-to-r from-[rgb(var(--primary-deep))]/35 via-[rgb(var(--accent-teal))]/20 to-[rgb(var(--accent-orange))]/25 p-8">
          <h1 className="page-title">OmniFlow AI</h1>
          <p className="page-subtitle">A conversion-optimized, AI-assisted revenue operations layer for vertical SMBs.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link className="focus-ring rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-[rgb(var(--primary-foreground))]" href="/dashboard">
              Open Dashboard
            </Link>
            <Link className="focus-ring rounded-xl border border-[rgb(var(--border))] px-4 py-2 text-sm font-semibold" href="/settings/integrations">
              Configure Integrations
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}



