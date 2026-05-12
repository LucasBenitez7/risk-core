import json

from channels.generic.websocket import AsyncWebsocketConsumer


class AuditEventsConsumer(AsyncWebsocketConsumer):
    GROUP = "audit_events"

    async def connect(self):
        if self.scope.get("user_id") is None:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def audit_event(self, event):
        await self.send(text_data=json.dumps(event["payload"], default=str))
