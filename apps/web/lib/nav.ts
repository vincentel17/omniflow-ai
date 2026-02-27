export type NavItem = {
  href: string;
  label: string;
  icon: string;
  realEstateOnly?: boolean;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

export const navSections: NavSection[] = [
  {
    title: "Growth",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "home" },
      { href: "/campaigns", label: "Campaigns", icon: "megaphone" },
      { href: "/content", label: "Content", icon: "pen" },
      { href: "/publish/jobs", label: "Publish Jobs", icon: "send" },
      { href: "/analytics", label: "Analytics", icon: "chart" }
    ]
  },
  {
    title: "Inbox",
    items: [
      { href: "/inbox", label: "Inbox", icon: "inbox" },
      { href: "/leads", label: "Leads", icon: "users" }
    ]
  },
  {
    title: "Optimize",
    items: [
      { href: "/optimization", label: "Optimization", icon: "sparkles" },
      { href: "/presence", label: "Presence", icon: "pulse" },
      { href: "/seo", label: "SEO", icon: "search" },
      { href: "/reputation", label: "Reputation", icon: "star" },
      { href: "/real-estate/deals", label: "Real Estate", icon: "building", realEstateOnly: true }
    ]
  },
  {
    title: "Settings",
    items: [
      { href: "/settings", label: "Org", icon: "settings" },
      { href: "/settings/verticals", label: "Vertical", icon: "layers" },
      { href: "/settings/integrations", label: "Integrations", icon: "plug" },
      { href: "/compliance", label: "Compliance", icon: "shield" },
      { href: "/events", label: "Events", icon: "list" }
    ]
  }
];
