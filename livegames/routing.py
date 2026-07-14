from django.urls import path

from .consumers import HostGameConsumer, ParticipantGameConsumer

websocket_urlpatterns = [
    path("ws/partidas/<int:game_id>/docente/", HostGameConsumer.as_asgi()),
    path("ws/partidas/<int:game_id>/participante/", ParticipantGameConsumer.as_asgi()),
]
