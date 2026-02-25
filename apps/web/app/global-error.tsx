"use client";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="page-shell">
          <div className="surface-card p-8 text-center">
            <p className="text-sm uppercase tracking-[0.14em] text-[rgb(var(--muted-foreground))]">Application error</p>
            <h1 className="mt-2 text-2xl font-semibold">Something went wrong</h1>
            <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{error.message || "Unknown error"}</p>
            <button className="focus-ring mt-6 rounded-xl border border-[rgb(var(--border))] px-4 py-2 text-sm" onClick={reset} type="button">
              Retry
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
