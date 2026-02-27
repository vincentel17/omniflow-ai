"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { navSections } from "../lib/nav";
import { cn } from "../lib/cn";
import { Badge, ButtonGhost } from "./ui/primitives";

type AppShellProps = {
  children: React.ReactNode;
  orgId: string;
  role: string;
  isRealEstate: boolean;
  envLabel: string;
  aiMode: string;
  connectorMode: string;
};

function AppIcon({ name }: { name: string }) {
  const common = "h-4 w-4";

  switch (name) {
    case "home":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M3 11.5 12 4l9 7.5V21h-6v-6H9v6H3z" fill="currentColor" /></svg>;
    case "chart":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M4 20V4h2v14h14v2zM10 16V9h2v7zm4 0V6h2v10zm4 0v-4h2v4z" fill="currentColor" /></svg>;
    case "settings":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="m19.4 13 .1-1-.1-1 2-1.6-2-3.4-2.3.7a7 7 0 0 0-1.7-1l-.4-2.4h-4l-.4 2.4c-.6.2-1.2.5-1.7 1L6 5.9 4 9.3 6 11l-.1 1 .1 1-2 1.6L6 18l2.3-.7c.5.4 1.1.7 1.7 1l.4 2.4h4l.4-2.4c.6-.2 1.2-.6 1.7-1l2.3.7 2-3.4zM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5" fill="currentColor" /></svg>;
    case "inbox":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M4 4h16v16H4zm2 2v8h3l2 3h2l2-3h3V6z" fill="currentColor" /></svg>;
    case "users":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M7.5 12A3.5 3.5 0 1 0 7.5 5a3.5 3.5 0 0 0 0 7m9 0A3.5 3.5 0 1 0 16.5 5a3.5 3.5 0 0 0 0 7M2 19.5c0-2.8 2.2-5 5-5h1c2.8 0 5 2.2 5 5V21H2zm11 1.5v-1.5c0-1.4-.5-2.7-1.3-3.7.8-.8 1.9-1.3 3.3-1.3h1c2.8 0 5 2.2 5 5V21z" fill="currentColor" /></svg>;
    case "megaphone":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M3 11v2h3l8 4V7l-8 4zm13-1h3v4h-3zm0-6h3v4h-3z" fill="currentColor" /></svg>;
    case "pen":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M4 16.5V20h3.5L18 9.5 14.5 6zM19.7 7.8c.4-.4.4-1 0-1.4l-2-2a1 1 0 0 0-1.4 0l-1.3 1.3 3.5 3.5z" fill="currentColor" /></svg>;
    case "send":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="m2 20 20-8L2 4v6l14 2-14 2z" fill="currentColor" /></svg>;
    case "sparkles":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="m12 3 1.5 3.5L17 8l-3.5 1.5L12 13l-1.5-3.5L7 8l3.5-1.5zM5 14l1 2.2L8 17l-2 .8L5 20l-.9-2.2L2 17l2.1-.8zM19 14l1 2.2 2 .8-2 .8-1 2.2-.9-2.2-2.1-.8 2.1-.8z" fill="currentColor" /></svg>;
    case "pulse":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M3 12h4l2-4 4 8 2-4h6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" /></svg>;
    case "building":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M4 20V6l8-3 8 3v14h-6v-4h-4v4z" fill="currentColor" /></svg>;
    case "layers":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5zm0 8 9 5-9 5-9-5z" fill="currentColor" /></svg>;
    case "plug":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M10 3v6H8v3a4 4 0 0 0 4 4v5h2v-5a4 4 0 0 0 4-4V9h-2V3h-2v6h-2V3z" fill="currentColor" /></svg>;
    case "shield":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="m12 3 8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6z" fill="currentColor" /></svg>;
    case "list":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M6 6h14v2H6zm0 5h14v2H6zm0 5h14v2H6zM2 6h2v2H2zm0 5h2v2H2zm0 5h2v2H2z" fill="currentColor" /></svg>;
    case "search":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="M10.5 3a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15m0 2a5.5 5.5 0 1 0 3.5 9.7L19 20l1.4-1.4-5-5A5.5 5.5 0 0 0 10.5 5" fill="currentColor" /></svg>;
    case "star":
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><path d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.3-5.7-3-5.7 3 1.1-6.3L2.8 9.7l6.4-.9z" fill="currentColor" /></svg>;
    default:
      return <svg aria-hidden className={common} viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="currentColor" /></svg>;
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const saved = window.localStorage.getItem("omniflow-theme");
    const next = saved === "light" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    setTheme(next);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    window.localStorage.setItem("omniflow-theme", next);
    setTheme(next);
  }

  return (
    <ButtonGhost aria-label="Toggle theme" onClick={toggle} type="button">
      {theme === "dark" ? "Light" : "Dark"}
    </ButtonGhost>
  );
}

function Breadcrumbs() {
  const pathname = usePathname();
  const crumbs = useMemo(() => pathname.split("/").filter(Boolean), [pathname]);

  if (crumbs.length === 0) {
    return <p className="text-sm text-[rgb(var(--muted-foreground))]">Home</p>;
  }

  return (
    <nav aria-label="Breadcrumb" className="text-sm text-[rgb(var(--muted-foreground))]">
      <ol className="flex flex-wrap items-center gap-2">
        <li>Home</li>
        {crumbs.map((crumb) => (
          <li className="flex items-center gap-2" key={crumb}>
            <span>/</span>
            <span className="capitalize">{crumb.replace(/-/g, " ")}</span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function NavContent({ isRealEstate }: { isRealEstate: boolean }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6 p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[rgb(var(--muted-foreground))]">OmniFlow AI</p>
        <p className="mt-1 text-lg font-semibold">Revenue Ops Console</p>
      </div>
      {navSections.map((section) => (
        <div key={section.title}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[rgb(var(--muted-foreground))]">{section.title}</p>
          <ul className="space-y-1">
            {section.items
              .filter((item) => (item.realEstateOnly ? isRealEstate : true))
              .map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <li key={item.href}>
                    <Link
                      className={cn(
                        "focus-ring flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition",
                        active
                          ? "bg-[rgb(var(--primary))]/15 text-[rgb(var(--foreground))]"
                          : "text-[rgb(var(--muted-foreground))] hover:bg-[rgb(var(--muted))] hover:text-[rgb(var(--foreground))]"
                      )}
                      href={item.href}
                    >
                      <AppIcon name={item.icon} />
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function AppShell({ children, orgId, role, isRealEstate, envLabel, aiMode, connectorMode }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <NavContent isRealEstate={isRealEstate} />
      </aside>

      <div className="app-main">
        <header className="app-topbar px-4 py-3 lg:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 lg:hidden">
              <ButtonGhost aria-label="Open navigation" onClick={() => setMobileNavOpen(true)} type="button">
                Menu
              </ButtonGhost>
            </div>
            <div className="flex min-w-0 flex-col gap-2">
              <Breadcrumbs />
              <p className="truncate text-xs text-[rgb(var(--muted-foreground))]">org: {orgId} | role: {role}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">{envLabel}</Badge>
              <Badge tone="warn">AI {aiMode}</Badge>
              <Badge tone="warn">Connector {connectorMode}</Badge>
              <ThemeToggle />
            </div>
          </div>
        </header>

        <div>{children}</div>
      </div>

      {mobileNavOpen ? (
        <div aria-modal="true" className="fixed inset-0 z-50 lg:hidden" role="dialog">
          <button className="absolute inset-0 bg-black/50" onClick={() => setMobileNavOpen(false)} type="button" />
          <div className="relative z-10 h-full w-[280px] overflow-y-auto bg-[rgb(var(--card))]">
            <div className="flex items-center justify-end p-3">
              <ButtonGhost onClick={() => setMobileNavOpen(false)} type="button">
                Close
              </ButtonGhost>
            </div>
            <NavContent isRealEstate={isRealEstate} />
          </div>
        </div>
      ) : null}
    </div>
  );
}




