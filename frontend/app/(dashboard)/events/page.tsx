import { EventFeed } from "@/components/events/EventFeed";

export default function EventsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Live events</h1>
        <p className="mt-1 text-sm text-slate-400">
          Real-time Kafka events streamed via WebSocket
        </p>
      </div>
      <EventFeed />
    </div>
  );
}
