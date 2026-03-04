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
      campaigns: []
    };

    await page.route("http://localhost:18000/**", async (route) => {
      const request = route.request();
      const { pathname } = new URL(request.url());
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

      return json({});
    });
  });

  test("J1 onboarding session starts and step completes", async ({ page }) => {
    await page.goto("/onboarding", { waitUntil: "domcontentloaded" });
    await page.getByTestId("onboarding-start").click();
    await expect(page.getByTestId("onboarding-step-select_vertical_pack")).toBeEnabled();
    await page.getByTestId("onboarding-step-select_vertical_pack").click();
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();
  });

  test("J3 inbox + leads primary actions update status", async ({ page }) => {
    await page.goto("/inbox", { waitUntil: "domcontentloaded" });
    await page.getByTestId("inbox-ingest-mock").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Mock inbound ingested");

    await page.locator("section").first().locator("ul li button").first().click();
    await page.getByTestId("inbox-suggest-reply").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Reply suggestion generated");
    await page.getByTestId("inbox-save-draft").click();
    await expect(page.getByTestId("inbox-status-message")).toContainText("Draft reply saved");
    await page.getByTestId("inbox-create-lead").click();
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

  test("J4 presence + seo + reputation actions update status", async ({ page }) => {
    await page.goto("/presence", { waitUntil: "domcontentloaded" });
    await page.getByTestId("presence-run-audit").click();
    await expect(page.getByTestId("presence-status-message")).toContainText("Presence audit completed");

    await page.goto("/seo", { waitUntil: "domcontentloaded" });
    await page.getByTestId("seo-generate-plan").click();
    await expect(page.getByTestId("seo-status-message")).toContainText("SEO plan generated");

    await page.goto("/reputation", { waitUntil: "domcontentloaded" });
    await page.getByTestId("reputation-import-mock-review").click();
    await expect(page.getByTestId("reputation-status-message")).toContainText("Review imported");
    await page.locator("[data-testid^='reputation-draft-response-']").first().click();
    await expect(page.getByTestId("reputation-status-message")).toContainText("Draft response generated");
  });

  test("J5/J6/J7 governance and diagnostics routes load", async ({ page }) => {
    await page.goto("/audit", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();

    await page.goto("/events", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();

    await page.goto("/billing", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Billing" })).toBeVisible();

    await page.goto("/automations/agents", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();

    await page.goto("/settings/integrations", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Connector Diagnostics" })).toBeVisible();
  });
});
