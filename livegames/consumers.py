from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import GameSession, Participant


class GameConsumerBase(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = f"game_{self.game_id}"
        if not await self.has_access():
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def game_event(self, event):
        await self.send_json({key: value for key, value in event.items() if key != "type"})


class HostGameConsumer(GameConsumerBase):
    @database_sync_to_async
    def has_access(self):
        user = self.scope["user"]
        return user.is_authenticated and GameSession.objects.filter(pk=self.game_id, host=user).exists()


class ParticipantGameConsumer(GameConsumerBase):
    @database_sync_to_async
    def has_access(self):
        session = self.scope.get("session")
        return bool(session and session.session_key and Participant.objects.filter(game_id=self.game_id, session_identifier=session.session_key).exists())
