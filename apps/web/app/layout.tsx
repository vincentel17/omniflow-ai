import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { AppShell } from "../components/app-shell";
import { ToastProvider } from "../components/ui/toast";
import { getApiBaseUrl, getRequestSessionContext } from "../lib/dev-context";
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

type RuntimeModes = {
  aiMode: string;
  connectorMode: string;
};

async function getRuntimeModes(orgId: string): Promise<RuntimeModes> {
  const fallback: RuntimeModes = {
    aiMode: process.env.NEXT_PUBLIC_AI_MODE ?? "mock",
    connectorMode: process.env.NEXT_PUBLIC_CONNECTOR_MODE ?? "mock"
  };

  try {
    const { cookies } = await import("next/headers");
    const store = await cookies();
    const cookieHeader = store
      .getAll()
      .map((entry) => `${entry.name}=${entry.value}`)
      .join("; ");

    if (!cookieHeader) {
      return fallback;
    }

    const response = await fetch(`${getApiBaseUrl()}/ops/settings`, {
      cache: "no-store",
      headers: {
        Cookie: cookieHeader,
        "X-Org-Id": orgId,
        "x-org-id": orgId
      }
    });

    if (!response.ok) {
      return fallback;
    }

    const payload = (await response.json()) as Partial<{ ai_mode: string; connector_mode: string }>;
    return {
      aiMode: payload.ai_mode ?? fallback.aiMode,
      connectorMode: payload.connector_mode ?? fallback.connectorMode
    };
  } catch {
    return fallback;
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await getRequestSessionContext();
  if (!session) {
    return (
      <html className="dark" lang="en" suppressHydrationWarning>
        <body className={inter.variable}>
          <ToastProvider>{children}</ToastProvider>
        </body>
      </html>
    );
  }

  const packSlug = await getCurrentPackSlugForSession(session);
  const runtimeModes = await getRuntimeModes(session.org_id);
  const isRealEstate = packSlug === "real-estate";

  return (
    <html className="dark" lang="en" suppressHydrationWarning>
      <body className={inter.variable}>
        <ToastProvider>
          <AppShell
            aiMode={runtimeModes.aiMode}
            connectorMode={runtimeModes.connectorMode}
            envLabel={envLabel()}
            isRealEstate={isRealEstate}
            orgName={session.org_id}
            role={session.role}
            sessionMode
          >
            {children}
          </AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
