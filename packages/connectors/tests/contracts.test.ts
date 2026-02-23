import { describe, expect, it } from "vitest";

import { MockPublisher } from "../src/mockPublisher";

describe("connector contract", () => {
  it("returns deterministic publish result", async () => {
    const adapter = new MockPublisher();
    const result = await adapter.publish({
      orgId: "org_123",
      channel: "linkedin",
      body: "hello"
    });

    expect(result).toEqual({ externalId: "mock-linkedin", status: "queued" });
  });
});
