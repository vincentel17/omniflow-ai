import Link from "next/link";

const links = [
  { href: "/settings/verticals", label: "Vertical Pack Selection", desc: "Choose active industry playbook and modules." },
  { href: "/settings/brand", label: "Brand Profile", desc: "Manage voice, tone, and publishing preferences." },
  { href: "/settings/integrations", label: "Integrations", desc: "Configure OAuth accounts and live toggles." },
  { href: "/settings/sla", label: "SLA", desc: "Set response and resolution targets." },
  { href: "/audit", label: "Audit Log", desc: "Review policy and operator actions." }
];

export default function SettingsPage() {
  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Organization controls, governance settings, and connector safety switches.</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {links.map((item) => (
          <Link className="surface-card p-5 transition hover:-translate-y-0.5 hover:shadow-lg" href={item.href} key={item.href}>
            <p className="font-semibold">{item.label}</p>
            <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{item.desc}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
