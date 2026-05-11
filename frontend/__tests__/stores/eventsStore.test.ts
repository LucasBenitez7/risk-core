import { beforeEach, describe, expect, it } from "vitest";
import { useEventsStore } from "@/lib/stores/eventsStore";
import type { KafkaEventMessage } from "@/lib/api/schemas";

const makeEvent = (i: number): KafkaEventMessage => ({
  id: `00000000-0000-0000-0000-${String(i).padStart(12, "0")}`,
  event_id: `00000000-0000-0000-0000-${String(i).padStart(12, "0")}`,
  event_type: `POLICY_CREATED_${i}`,
  kafka_topic: "policy-service",
  entity_type: "policy",
  entity_id: `00000000-0000-0000-0000-${String(i).padStart(12, "0")}`,
  service: "policy-service",
  occurred_at: new Date().toISOString(),
  received_at: new Date().toISOString(),
  payload: { id: String(i) },
});

beforeEach(() => {
  useEventsStore.getState().clear();
});

describe("eventsStore", () => {
  it("pushes events to the front", () => {
    const { push } = useEventsStore.getState();
    push(makeEvent(1));
    push(makeEvent(2));
    const { events } = useEventsStore.getState();
    expect(events[0]?.event_type).toBe("POLICY_CREATED_2");
    expect(events[1]?.event_type).toBe("POLICY_CREATED_1");
  });

  it("caps at MAX_EVENTS (500)", () => {
    const { push } = useEventsStore.getState();
    for (let i = 0; i < 502; i++) push(makeEvent(i));
    expect(useEventsStore.getState().events.length).toBe(500);
  });

  it("clears all events", () => {
    const { push, clear } = useEventsStore.getState();
    push(makeEvent(1));
    clear();
    expect(useEventsStore.getState().events).toHaveLength(0);
  });
});
