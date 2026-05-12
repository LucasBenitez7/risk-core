import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { EventStreamClient } from "@/lib/ws/client";

class MockWebSocket {
  static instance: MockWebSocket | null = null;
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instance = this;
  }

  close() {
    this.closed = true;
    this.onclose?.();
  }
}

function stubWsTokenFetch(token: string | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: token !== null,
      json: () => Promise.resolve(token !== null ? { token } : {}),
    }),
  );
}

beforeEach(() => {
  MockWebSocket.instance = null;
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("EventStreamClient", () => {
  it("fetches ws-token and connects with it in URL", async () => {
    stubWsTokenFetch("my-token");
    const client = new EventStreamClient(vi.fn(), vi.fn());
    await client.connect();
    expect(MockWebSocket.instance?.url).toContain("token=my-token");
    client.destroy();
  });

  it("calls onState('open') when socket opens", async () => {
    stubWsTokenFetch("tok");
    const onState = vi.fn();
    const client = new EventStreamClient(vi.fn(), onState);
    await client.connect();
    MockWebSocket.instance?.onopen?.();
    expect(onState).toHaveBeenCalledWith("open");
    client.destroy();
  });

  it("calls onMessage with parsed KafkaEventMessage", async () => {
    stubWsTokenFetch("tok");
    const onMsg = vi.fn();
    const client = new EventStreamClient(onMsg, vi.fn());
    await client.connect();
    const payload = {
      id: "11111111-1111-1111-1111-111111111111",
      event_id: "22222222-2222-2222-2222-222222222222",
      event_type: "POLICY_CREATED",
      kafka_topic: "policy-service",
      entity_type: "policy",
      entity_id: "33333333-3333-3333-3333-333333333333",
      service: "policy-service",
      occurred_at: new Date().toISOString(),
      received_at: new Date().toISOString(),
      payload: { id: "abc" },
    };
    MockWebSocket.instance?.onmessage?.({ data: JSON.stringify(payload) });
    expect(onMsg).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: "POLICY_CREATED" }),
    );
    client.destroy();
  });

  it("ignores malformed messages", async () => {
    stubWsTokenFetch("tok");
    const onMsg = vi.fn();
    const client = new EventStreamClient(onMsg, vi.fn());
    await client.connect();
    MockWebSocket.instance?.onmessage?.({ data: "not-json{{" });
    expect(onMsg).not.toHaveBeenCalled();
    client.destroy();
  });

  it("does not open WebSocket if ws-token endpoint returns 401", async () => {
    stubWsTokenFetch(null);
    const client = new EventStreamClient(vi.fn(), vi.fn());
    await client.connect();
    expect(MockWebSocket.instance).toBeNull();
    client.destroy();
  });
});
