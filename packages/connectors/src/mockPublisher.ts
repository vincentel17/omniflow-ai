import type { PublishPayload, PublishResult, SocialPublisher } from "./contracts";

export class MockPublisher implements SocialPublisher {
  async publish(payload: PublishPayload): Promise<PublishResult> {
    if (!payload.orgId) {
      throw new Error("orgId is required");
    }

    return {
      externalId: `mock-${payload.channel}`,
      status: "queued"
    };
  }
}
