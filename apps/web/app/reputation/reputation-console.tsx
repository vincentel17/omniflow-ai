"use client";

import { useState } from "react";

import { getApiBaseUrl } from "../../lib/dev-context";

type Review = {
  id: string;
  rating: number;
  reviewer_name_masked: string;
  review_text: string;
  sentiment_json: { urgency?: string; labels?: string[] };
};

type Campaign = {
  id: string;
  name: string;
  status: string;
  audience: string;
  channel: string;
};

type Props = {
  initialReviews: Review[];
  initialCampaigns: Campaign[];
};

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json"
  };
}

export function ReputationConsole({ initialReviews, initialCampaigns }: Props) {
  const [reviews, setReviews] = useState<Review[]>(initialReviews);
  const [campaigns, setCampaigns] = useState<Campaign[]>(initialCampaigns);
  const [status, setStatus] = useState<string | null>(null);
  const [draftByReview, setDraftByReview] = useState<Record<string, string>>({});
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  async function refresh() {
    setPendingAction("refresh");
    setStatus(null);
    try {
      const [reviewsRes, campaignsRes] = await Promise.all([
        fetch(`${getApiBaseUrl()}/reputation/reviews?limit=50&offset=0`, { headers: headers(), cache: "no-store", credentials: "include" }),
        fetch(`${getApiBaseUrl()}/reputation/campaigns?limit=50&offset=0`, { headers: headers(), cache: "no-store", credentials: "include" })
      ]);
      if (!reviewsRes.ok || !campaignsRes.ok) {
        setStatus("Refresh failed.");
        return;
      }
      setReviews((await reviewsRes.json()) as Review[]);
      setCampaigns((await campaignsRes.json()) as Campaign[]);
    } catch {
      setStatus("Refresh failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function importMockReview() {
    setPendingAction("import");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/reputation/reviews/import`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
        body: JSON.stringify({
          reviews: [
            {
              source: "manual_import",
              reviewer_name: "Customer",
              rating: 2,
              review_text: "Response time was slow and pricing unclear."
            }
          ]
        })
      });
      if (!response.ok) {
        setStatus(`Import failed (${response.status})`);
        return;
      }
      setStatus("Review imported.");
      await refresh();
    } catch {
      setStatus("Import failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function draftResponse(reviewId: string) {
    setPendingAction(`draft-${reviewId}`);
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/reputation/reviews/${reviewId}/draft-response`, {
        method: "POST",
        headers: headers(),
        credentials: "include"
      });
      if (!response.ok) {
        setStatus(`Draft failed (${response.status})`);
        return;
      }
      const payload = (await response.json()) as { response_text: string };
      setDraftByReview((prev) => ({ ...prev, [reviewId]: payload.response_text }));
      setStatus("Draft response generated.");
    } catch {
      setStatus("Draft failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function createCampaign() {
    setPendingAction("campaign");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/reputation/campaigns`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
        body: JSON.stringify({
          name: `Review Request ${new Date().toISOString()}`,
          audience: "recent_customers",
          template_key: "review_request_v1",
          channel: "email"
        })
      });
      if (!response.ok) {
        setStatus(`Campaign create failed (${response.status})`);
        return;
      }
      const campaign = (await response.json()) as Campaign;
      const start = await fetch(`${getApiBaseUrl()}/reputation/campaigns/${campaign.id}/start`, {
        method: "POST",
        headers: headers(),
        credentials: "include"
      });
      if (!start.ok) {
        setStatus(`Campaign start failed (${start.status})`);
        return;
      }
      setStatus("Campaign started and tasks created.");
      await refresh();
    } catch {
      setStatus("Campaign failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="mt-6 space-y-6">
      <section className="rounded border border-slate-800 p-4">
        <div className="flex gap-2">
          <button
            className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900"
            data-testid="reputation-import-mock-review"
            disabled={pendingAction !== null}
            onClick={importMockReview}
            type="button"
          >
            {pendingAction === "import" ? "Importing..." : "Import Mock Review"}
          </button>
          <button
            className="rounded bg-slate-700 px-3 py-1 text-sm"
            data-testid="reputation-create-start-campaign"
            disabled={pendingAction !== null}
            onClick={createCampaign}
            type="button"
          >
            {pendingAction === "campaign" ? "Starting..." : "Create + Start Campaign"}
          </button>
        </div>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Reviews</h2>
        <ul className="mt-3 space-y-2">
          {reviews.map((review) => (
            <li className="rounded border border-slate-700 p-3" key={review.id}>
              <p className="font-medium">
                {review.reviewer_name_masked} | {review.rating} stars
              </p>
              <p className="text-sm text-slate-400">{review.review_text}</p>
              <p className="text-xs text-slate-500">Urgency: {review.sentiment_json.urgency ?? "n/a"}</p>
              <button
                className="mt-2 rounded bg-slate-700 px-3 py-1 text-sm"
                data-testid={reviews[0]?.id === review.id ? "tour-reputation-draft-response" : `reputation-draft-response-${review.id}`}
                disabled={pendingAction !== null}
                onClick={() => draftResponse(review.id)}
                type="button"
              >
                {pendingAction === `draft-${review.id}` ? "Drafting..." : "Draft Response"}
              </button>
              {draftByReview[review.id] ? <p className="mt-2 text-sm text-slate-300">{draftByReview[review.id]}</p> : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Campaigns</h2>
        <ul className="mt-3 space-y-2">
          {campaigns.map((campaign) => (
            <li className="rounded border border-slate-700 p-3" key={campaign.id}>
              <p className="font-medium">{campaign.name}</p>
              <p className="text-sm text-slate-400">
                {campaign.status} | {campaign.audience} | {campaign.channel}
              </p>
            </li>
          ))}
        </ul>
      </section>
      {status ? <p className="text-sm text-slate-300" data-testid="reputation-status-message">{status}</p> : null}
    </div>
  );
}
