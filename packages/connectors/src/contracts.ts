export type PublishPayload = {
  orgId: string;
  channel: "facebook" | "instagram" | "linkedin" | "google-business-profile";
  body: string;
};

export type PublishResult = {
  externalId: string;
  status: "queued" | "published";
};

export interface SocialPublisher {
  publish(payload: PublishPayload): Promise<PublishResult>;
}
