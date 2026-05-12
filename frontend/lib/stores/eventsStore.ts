"use client";

import { create } from "zustand";
import type { KafkaEventMessage } from "@/lib/api/schemas";

const MAX_EVENTS = 500;

interface EventsState {
  events: KafkaEventMessage[];
  push: (event: KafkaEventMessage) => void;
  clear: () => void;
}

export const useEventsStore = create<EventsState>()((set) => ({
  events: [],
  push: (event) =>
    set((state) => ({
      events:
        state.events.length >= MAX_EVENTS
          ? [event, ...state.events.slice(0, MAX_EVENTS - 1)]
          : [event, ...state.events],
    })),
  clear: () => set({ events: [] }),
}));
