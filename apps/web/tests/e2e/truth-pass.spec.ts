import { expect, test } from "@playwright/test";

test.describe("truth pass core journeys (mock mode)", () => {
  test.beforeEach(async ({ page }) => {
    const now = "2026-03-04T12:00:00.000Z";
    const state = {
      onboarding:
        null as
          | {
              id: string;
              status: "in_progress" | "completed";
              steps_json: Record<string, boolean>;
              created_at: string;
              completed_at: string | null;
            }
          | null,
      threads: [
        {
          id: "thread-1",
          provider: "meta",
          account_ref: "acct-main",
          subject: "Mock inbound",
          status: "open",
          assigned_to_user_id: null,
          last_message_at: now,
          lead_id: null
        }
      ],
      messages: [
        {
          id: "msg-1",
          direction: "inbound",
          sender_display: "Prospect",
          body_text: "Need help buying soon.",
          created_at: now,
          flags_json: {}
        }
      ],
      leads: [
        {
          id: "lead-1",
          source: "inbox",
          status: "new",
          name: "Mock Lead",
          email: "lead@example.test",
          phone: null,
          tags_json: [],
          created_at: now
        }
      ],
      leadTasks: [
        {
          id: "task-1",
          type: "send_message",
          due_at: now,
          status: "pending",
          template_key: "nurture_v1"
        }
      ],
      presenceLatest: {
        id: "presence-1",
        status: "completed",
        summary_scores_json: { overall_score: 82, category_scores: { listings: 80 } },
        created_at: now
      },
      presenceFindings: [
        {
          id: "finding-1",
          source: "gbp",
          category: "listings",
          severity: "medium",
          title: "Business hours mismatch",
          status: "open"
        }
      ],
      presenceTasks: [
        { id: "presence-task-1", type: "fix_hours", status: "pending", payload_json: {} }
      ],
      seoWorkItems: [
        {
          id: "seo-1",
          type: "service_page",
          status: "draft",
          target_keyword: "seattle home care",
          url_slug: "seattle-home-care",
          rendered_markdown: null
        }
      ],
      reviews: [
        {
          id: "review-1",
          rating: 2,
          reviewer_name_masked: "C***",
          review_text: "Slow response time.",
          sentiment_json: { urgency: "high", labels: ["response_time"] }
        }
      ],
      campaigns: [
        {
          id: "campaign-1",
          week_start_date: "2026-03-02",
          status: "draft",
          vertical_pack_slug: "generic",
          created_at: now
        }
      ],
      content: [
        {
          id: "content-1",
          campaign_plan_id: "campaign-1",
          channel: "facebook",
          status: "draft",
          risk_tier: "low",
          policy_warnings_json: [],
          created_at: now
        }
      ],
      publishJobs: [
        {
          id: "publish-1",
          content_id: "content-1",
          channel: "facebook",
          provider: "meta",
          status: "scheduled",
          scheduled_for: "2026-03-05T15:00:00.000Z",
          published_at: null,
          external_id: null
        }
      ],
      opsSettings: {
        env: "development",
        auto_post_enabled: false,
        require_approvals: true
      },
      auditEntries: [
        {
          id: "audit-1",
          actor_user_id: "owner-1",
          entity_type: "campaign_plan",
          entity_id: "campaign-1",
          action: "CAMPAIGN_PLANNED",
          metadata_json: {},
          created_at: now
        }
      ],
      events: [
        {
          id: "event-1",
          type: "CAMPAIGN_PLANNED",
          entity_type: "campaign_plan",
          entity_id: "campaign-1",
          payload_json: {},
          created_at: now
        }
      ],
      billing: {
        plan_name: "Growth",
        status: "active",
        period_end: "2026-04-01T00:00:00.000Z",
        usage: { posts: 4, workflows: 2 }
      },
      agents: [
        { id: "agent-run-1", org_id: "org-1", agent_name: "SupervisorAgent", trigger_type: "manual", status: "planned", started_at: now, finished_at: null, created_at: now }
      ],
      diagnostics: {
        connector_mode: "mock",
        ai_mode: "mock",
        ads_mode: "mock",
        live_ready: false,
        env_checks: [
          { key: "GOOGLE_CLIENT_ID", required_for_live: true, present: false },
          { key: "META_APP_ID", required_for_live: true, present: false }
        ],
        accounts_linked: 1,
        last_sync_at: now,
        last_error: null
      }
    };

    await page.route("http://localhost:18000/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const pathname = url.pathname;
      const method = request.method();

      const json = async (payload: unknown, status = 200) =>
        route.fulfill({
          status,
          contentType: "application/json",
          body: JSON.stringify(payload)
        });

      if (pathname === "/onboarding/status" && method === "GET") return json(state.onboarding);
      if (pathname === "/onboarding/start" && method === "POST") {
        state.onboarding = {
          id: "onboarding-1",
          status: "in_progress",
          steps_json: {},
          created_at: now,
          completed_at: null
        };
        return json(state.onboarding);
      }
      if (pathname.startsWith("/onboarding/step/") && pathname.endsWith("/complete") && method === "POST") {
        if (!state.onboarding) return json({ detail: "No session" }, 400);
        const stepId = pathname.replace("/onboarding/step/", "").replace("/complete", "");
        state.onboarding.steps_json[stepId] = true;
        return json(state.onboarding);
      }

      if (pathname === "/campaigns" && method === "GET") return json(state.campaigns);
      if (pathname === "/campaigns/plan" && method === "POST") {
        const next = {
          id: `campaign-${state.campaigns.length + 1}`,
          week_start_date: "2026-03-09",
          status: "draft",
          vertical_pack_slug: "generic",
          created_at: now
        };
        state.campaigns.unshift(next);
        return json(next);
      }
      if (pathname.startsWith("/campaigns/") && pathname.endsWith("/generate-content") && method === "POST") {
        const campaignId = pathname.split("/")[2];
        const generated = {
          id: `content-${state.content.length + 1}`,
          campaign_plan_id: campaignId,
          channel: "facebook",
          title: `Generated Draft ${state.content.length + 1}`,
          body: "Generated draft body.",
          status: "draft",
          risk_tier: "low",
          policy_warnings_json: [],
          created_at: now,
          scheduled_for: null
        };
        state.content.unshift(generated);
        return json({ created_items: [generated.id], count: 1 });
      }
      if (pathname.startsWith("/campaigns/") && pathname.endsWith("/approve") && method === "POST") {
        return json({ ok: true });
      }

      if (pathname === "/content" && method === "GET") return json(state.content);
      if (pathname.startsWith("/content/") && pathname.endsWith("/approve") && method === "POST") {
        const id = pathname.split("/")[2];
        const item = state.content.find((entry) => entry.id === id);
        if (item) item.status = "approved";
        return json(item ?? { id, status: "approved" });
      }
      if (pathname.startsWith("/content/") && pathname.endsWith("/schedule") && method === "POST") {
        const id = pathname.split("/")[2];
        const item = state.content.find((entry) => entry.id === id);
        if (item) item.status = "scheduled";
        const job = {
          id: `publish-${state.publishJobs.length + 1}`,
          content_id: id,
          channel: item?.channel ?? "facebook",
          provider: "meta",
          status: "scheduled",
          scheduled_for: "2026-03-05T17:00:00.000Z",
          published_at: null,
          external_id: null
        };
        state.publishJobs.unshift(job);
        return json(job);
      }

      if (pathname === "/publish/jobs" && method === "GET") return json(state.publishJobs);
      if (pathname === "/ops/settings" && method === "GET") return json(state.opsSettings);

      if (pathname === "/inbox/threads" && method === "GET") return json(state.threads);
      if (pathname.startsWith("/inbox/threads/") && pathname.endsWith("/messages") && method === "GET") return json(state.messages);
      if (pathname === "/inbox/ingest/mock" && method === "POST") return json({ ok: true });
      if (pathname.includes("/suggest-reply") && method === "POST") return json({ reply_text: "Thanks for reaching out, happy to help." });
      if (pathname.includes("/draft-reply") && method === "POST") return json({ id: "draft-1" });
      if (pathname.startsWith("/leads/from-thread/") && method === "POST") {
        if (!state.leads.find((lead) => lead.id === "lead-created")) {
          state.leads.unshift({
            id: "lead-created",
            source: "inbox",
            status: "new",
            name: "Thread Lead",
            email: "thread@example.test",
            phone: null,
            tags_json: [],
            created_at: now
          });
        }
        return json({ id: "lead-created" });
      }

      if (pathname === "/leads" && method === "GET") return json(state.leads);
      if (pathname.includes("/leads/") && pathname.endsWith("/score") && method === "POST") {
        return json({ score_total: 83, score_json: { fit: 0.8, intent: 0.86 } });
      }
      if (pathname.includes("/leads/") && pathname.endsWith("/route") && method === "POST") {
        return json({ assigned_to_user_id: "owner-1", rule_applied: "round_robin" });
      }
      if (pathname.includes("/nurture/suggest") && method === "POST") {
        return json({ tasks: [{ type: "send_message", due_in_minutes: 15 }] });
      }
      if (pathname.includes("/nurture/apply") && method === "POST") return json({ created: 1 });
      if (pathname.includes("/nurture/tasks") && method === "GET") return json(state.leadTasks);
      if (pathname.includes("/optimization/next-best-action/") && method === "GET") {
        return json({
          action_type: "call_now",
          rationale: "High intent and recent activity",
          expected_uplift: 0.24,
          confidence_score: 0.81
        });
      }

      if (pathname === "/presence/audits/run" && method === "POST") return json({ id: "presence-1" });
      if (pathname === "/presence" && method === "GET") return json(state.presenceLatest);
      if (pathname === "/presence/findings" && method === "GET") return json(state.presenceFindings);
      if (pathname === "/presence/tasks" && method === "GET") return json(state.presenceTasks);

      if (pathname === "/seo/plan" && method === "POST") return json({ service_pages: [{ keyword: "seattle home care", slug: "seattle-home-care" }] });
      if (pathname === "/seo/work-items" && method === "GET") return json(state.seoWorkItems);
      if (pathname === "/seo/work-items" && method === "POST") return json(state.seoWorkItems[0]);

      if (pathname === "/reputation/reviews/import" && method === "POST") return json({ imported: 1 });
      if (pathname === "/reputation/reviews" && method === "GET") return json(state.reviews);
      if (pathname === "/reputation/campaigns" && method === "GET") return json(state.campaigns);
      if (pathname.includes("/reputation/reviews/") && pathname.endsWith("/draft-response") && method === "POST") {
        return json({ response_text: "Thanks for the feedback. We are improving response times." });
      }

      if (pathname === "/audit" && method === "GET") return json(state.auditEntries);
      if (pathname === "/events" && method === "GET") return json(state.events);
      if (pathname === "/billing/subscription" && method === "GET") return json(state.billing);
      if (pathname === "/billing/plans" && method === "GET") return json([{ id: "plan-growth", name: "Growth", price_monthly_usd: 199 }]);
      if (pathname === "/billing/status" && method === "GET") return json({ org_status: "active", subscription_status: "active" });
      if (pathname === "/agents/context" && method === "GET") return json({ snapshot: { org_id: "org-1", active_pack_slug: "generic", modes: { ai_mode: "mock", connector_mode: "mock" }, entitlements_summary: { workflows: true }, compliance_mode: "none", risk_limits: { max_auto_tier: 1 }, recent_events_summary: { CAMPAIGN_PLANNED: 1 }, inbox_summary: { open_threads: 1 }, leads_summary: { new: 2 }, optimization_signals: { predictive_lead_lift: 0.22 }, presence_summary: { latest_score: 82 }, seo_summary: { drafts_pending: 1 }, reputation_summary: { unresponded_negative_reviews: 1 } } });
      if (pathname === "/agents/definitions" && method === "GET") return json([
        { id: "agent-def-1", name: "SupervisorAgent", version: "1.0.0", enabled: true, supported_packs_json: ["generic"], config_json: {}, created_at: now },
        { id: "agent-def-2", name: "InboxAgent", version: "1.0.0", enabled: true, supported_packs_json: ["generic"], config_json: {}, created_at: now }
      ]);
      if (pathname === "/agents/run" && method === "POST") return json({ id: "agent-run-1", org_id: "org-1", agent_name: "SupervisorAgent", agent_version: "1.0.0", trigger_type: "manual", status: "planned", context_snapshot_json: { org_id: "org-1", active_pack_slug: "generic", modes: { ai_mode: "mock", connector_mode: "mock" }, entitlements_summary: {}, compliance_mode: "none", risk_limits: { max_auto_tier: 1 }, recent_events_summary: {}, inbox_summary: {}, leads_summary: {}, optimization_signals: {}, presence_summary: {}, seo_summary: {}, reputation_summary: {} }, perception_json: { observations: [] }, plan_json: { plan_id: "plan-1", steps: [] }, started_at: now, finished_at: null, error_json: {}, created_at: now });
      if (pathname === "/agents/runs" && method === "GET") return json(state.agents);
      if (pathname === "/connectors/diagnostics/summary" && method === "GET") return json(state.diagnostics);

      return json({});
    });
  });

  test("J1 onboarding session starts and pack step completes", async ({ page }) => {
    await page.goto("/onboarding", { waitUntil: "domcontentloaded" });
    await page.getByTestId("tour-onboarding-create-org").click();
    await expect(page.getByTestId("tour-pack-select")).toBeEnabled();
    await page.getByTestId("tour-pack-select").click();
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();
  });

  test("J2 campaign to draft approval to publish scheduling", async ({ page }) => {
    await page.goto("/campaigns", { waitUntil: "domcontentloaded" });
    const campaignRows = page.getByTestId("campaign-list").locator("li");
    const initialCampaignCount = await campaignRows.count();
    await page.getByTestId("tour-campaign-create").click();
    await expect(page.getByTestId("campaign-status-message")).toContainText("Campaign plan created.");
    await expect(page.getByTestId("campaign-list").locator("li")).toHaveCount(initialCampaignCount + 1);
    await page.getByTestId("tour-drafts-generate").click();
    await expect(page.getByTestId("campaign-status-message")).toContainText("Content generated.");

    await page.goto("/content", { waitUntil: "domcontentloaded" });
    const contentRows = page.getByTestId("content-list").locator("li");
    await expect(contentRows.first()).toContainText("draft");
    await page.getByTestId("tour-drafts-approve").click();
    await expect(page.getByTestId("content-status-message")).toContainText("Content approved.");
    await expect(contentRows.first()).toContainText("approved");
    await page.getByTestId("tour-publish-schedule").click();
    await expect(page.getByTestId("content-status-message")).toContainText("Publish job queued.");
    await expect(contentRows.first()).toContainText("scheduled");

    await page.goto("/publish/jobs", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Publish Jobs" })).toBeVisible();
    await expect(page.getByTestId("publish-jobs-list").locator("li").first()).toContainText("scheduled");
  });
  test("J3 inbox and leads actions update state", async ({ page }) => {
    await page.goto("/inbox", { waitUntil: "domcontentloaded" });
    await page.getByTestId("inbox-ingest-mock").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Mock inbound ingested");
    await page.getByTestId("tour-inbox-open-thread").click();
    await page.getByTestId("inbox-suggest-reply").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Reply suggestion generated");
    await page.getByTestId("tour-inbox-send-reply").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Draft reply saved");
    await page.getByTestId("tour-lead-create").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Lead created from thread");

    await page.goto("/leads", { waitUntil: "domcontentloaded" });
    await page.getByTestId("leads-refresh").click();
    await page.locator("section").first().locator("ul li button").first().click();
    await page.getByTestId("lead-score-btn").click();
    await expect(page.getByTestId("lead-status-message")).toContainText("Lead scored");
    await page.getByTestId("lead-route-btn").click();
    await expect(page.getByTestId("lead-status-message")).toContainText("Lead routed");
    await page.getByTestId("lead-apply-nurture-btn").click();
    await expect(page.getByTestId("lead-status-message")).toContainText("Nurture tasks applied");
  });

  test("J4 presence, seo, and reputation actions update status", async ({ page }) => {
    await page.goto("/presence", { waitUntil: "domcontentloaded" });
    await page.getByTestId("tour-presence-run").click();
    await expect(page.getByTestId("presence-status-message")).toContainText("Presence audit completed");

    await page.goto("/seo", { waitUntil: "domcontentloaded" });
    await page.getByTestId("tour-seo-create-task").click();
    await expect(page.getByTestId("seo-status-message")).toContainText("SEO plan generated");

    await page.goto("/reputation", { waitUntil: "domcontentloaded" });
    await page.getByTestId("reputation-import-mock-review").click();
    await expect(page.getByTestId("reputation-status-message")).toContainText("Review imported");
    await page.getByTestId("tour-reputation-draft-response").click();
    await expect(page.getByTestId("reputation-status-message")).toContainText("Draft response generated");
  });

  test("J5 governance, billing, agents, and diagnostics pages load", async ({ page }) => {
    await page.goto("/audit", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("tour-audit-open")).toBeVisible();

    await page.goto("/analytics", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("tour-analytics-open")).toBeVisible();

    await page.goto("/billing", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Billing" })).toBeVisible();

    await page.goto("/automations/agents", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
    await page.getByTestId("tour-agent-run").click();

    await page.goto("/settings/integrations/diagnostics", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Integration Diagnostics" })).toBeVisible();
    await expect(page.getByText("Connector mode")).toBeVisible();
  });
});





