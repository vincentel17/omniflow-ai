import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { getDevContext } from "../lib/dev-context";

export const metadata: Metadata = {
  title: "OmniFlow AI",
  description: "Conversion-optimized AI-assisted revenue operations layer"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const context = getDevContext();
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-800 bg-slate-950 px-6 py-4 text-slate-100">
          <div className="mx-auto flex max-w-6xl items-center justify-between">
            <nav className="flex gap-4 text-sm">
              <Link href="/dashboard">Dashboard</Link>
              <Link href="/settings">Settings</Link>
              <Link href="/settings/verticals">Verticals</Link>
              <Link href="/events">Events</Link>
              <Link href="/audit">Audit</Link>
            </nav>
            <p className="text-xs text-slate-400">
              org: {context.orgId} • role: {context.role}
            </p>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
