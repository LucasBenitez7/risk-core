"use client";

import { useEffect, useRef, useState } from "react";
import { EventStreamClient } from "@/lib/ws/client";
import { useEventsStore } from "@/lib/stores/eventsStore";
import { useAuth } from "@/lib/hooks/useAuth";

export type ConnectionState = "connecting" | "open" | "closed" | "idle";

export function useEventStream() {
  const { isAuthenticated } = useAuth();
  const push = useEventsStore((s) => s.push);
  const [connState, setConnState] = useState<ConnectionState>("idle");
  const clientRef = useRef<EventStreamClient | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;

    const client = new EventStreamClient(push, setConnState);
    clientRef.current = client;
    void client.connect();

    return () => {
      client.destroy();
      clientRef.current = null;
    };
  }, [isAuthenticated, push]);

  return { connState };
}
