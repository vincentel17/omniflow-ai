import { apiFetch } from "../../lib/api";
import { ReputationConsole } from "./reputation-console";

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

export default async function ReputationPage() {
  const reviews = await apiFetch<Review[]>("/reputation/reviews?limit=50&offset=0");
  const campaigns = await apiFetch<Campaign[]>("/reputation/campaigns?limit=50&offset=0");
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Reputation Manager</h1>
      <p className="mt-2 text-slate-400">Import reviews, score sentiment, draft responses, and run request campaigns.</p>
      <ReputationConsole initialReviews={reviews} initialCampaigns={campaigns} />
    </main>
  );
}
