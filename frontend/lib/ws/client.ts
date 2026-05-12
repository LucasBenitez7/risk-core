"use client";

import {
  kafkaEventMessageSchema,
  type KafkaEventMessage,
} from "@/lib/api/schemas";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8080/ws/events/";

type MessageHandler = (msg: KafkaEventMessage) => void;
type StateHandler = (state: "connecting" | "open" | "closed") => void;

/**
 * Fetches a short-lived access token from the Next.js auth route, which
 * reads it from the httpOnly cookie. The token is used as the WS query
 * param (`?token=`) and is not persisted anywhere.
 */
async function fetchWsToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/ws-token");
    if (!res.ok) return null;
    const data = (await res.json()) as { token?: string };
    return data.token ?? null;
  } catch {
    return null;
  }
}

export class EventStreamClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoffMs = 1_000;
  private destroyed = false;
  private onMessage: MessageHandler;
  private onState: StateHandler;

  constructor(onMessage: MessageHandler, onState: StateHandler) {
    this.onMessage = onMessage;
    this.onState = onState;
  }

  async connect() {
    if (this.destroyed) return;
    this.onState("connecting");

    const token = await fetchWsToken();
    if (this.destroyed) return;
    if (!token) {
      this.onState("closed");
      this.scheduleReconnect();
      return;
    }

    const url = `${WS_URL}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.backoffMs = 1_000;
      this.onState("open");
    };

    ws.onmessage = (evt) => {
      try {
        const raw = JSON.parse(evt.data as string);
        const parsed = kafkaEventMessageSchema.safeParse(raw);
        if (parsed.success) this.onMessage(parsed.data);
      } catch {
        /* malformed frame */
      }
    };

    ws.onclose = () => {
      this.ws = null;
      if (!this.destroyed) {
        this.onState("closed");
        this.scheduleReconnect();
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  private scheduleReconnect() {
    const delay = Math.min(this.backoffMs, 30_000);
    this.backoffMs = Math.min(this.backoffMs * 2, 30_000);
    this.reconnectTimer = setTimeout(() => {
      void this.connect();
    }, delay);
  }

  destroy() {
    this.destroyed = true;
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}
