import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page-shell">
      <div className="surface-card p-8 text-center">
        <p className="text-sm uppercase tracking-[0.14em] text-[rgb(var(--muted-foreground))]">404</p>
        <h1 className="mt-2 text-3xl font-semibold">Page not found</h1>
        <p className="mt-2 text-[rgb(var(--muted-foreground))]">The route does not exist in this environment.</p>
        <Link className="focus-ring mt-6 inline-block rounded-xl border border-[rgb(var(--border))] px-4 py-2 text-sm" href="/dashboard">
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
