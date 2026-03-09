import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { AppShell } from "../components/app-shell";
import { ToastProvider } from "../components/ui/toast";
import { getRequestSessionContext } from "../lib/dev-context";
import { getCurrentPackSlugForSession } from "../lib/vertical-pack";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "OmniFlow AI",
  description: "Conversion-optimized AI-assisted revenue operations layer"
};

export const dynamic = "force-dynamic";

function envLabel(): string {
  const env = (process.env.NODE_ENV ?? "development").toUpperCase();
  if (env === "PRODUCTION") return "PROD";
  if (env === "TEST") return "STAGING";
  return "DEV";
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await getRequestSessionContext();
  const packSlug = await getCurrentPackSlugForSession(session);
  const isRealEstate = packSlug === "real-estate";
  const effectiveOrgName = session?.org_id ?? "unauthenticated";
  const effectiveRole = session?.role ?? "guest";

  return (
    <html className="dark" lang="en" suppressHydrationWarning>
      <body className={inter.variable}>
        <ToastProvider>
          <AppShell
            aiMode={process.env.NEXT_PUBLIC_AI_MODE ?? "mock"}
            connectorMode={process.env.NEXT_PUBLIC_CONNECTOR_MODE ?? "mock"}
            envLabel={envLabel()}
            isRealEstate={isRealEstate}
            orgName={effectiveOrgName}
            role={effectiveRole}
            sessionMode={Boolean(session)}
          >
            {children}
          </AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
