from django.urls import path

from . import views

app_name = "livegames"

urlpatterns = [
    path("crear/", views.game_create, name="create"),
    path("historial/", views.game_history, name="history"),
    path("ingresar/", views.join_pin, name="join_pin"),
    path("ingresar/<str:pin>/", views.join_nickname, name="join_nickname"),
    path("<int:pk>/docente/", views.host_room, name="host_room"),
    path("<int:pk>/docente/modo-proyeccion/", views.toggle_projection_mode, name="toggle_projection_mode"),
    path("<int:pk>/accion/<str:action>/", views.host_action, name="host_action"),
    path("<int:pk>/jugar/", views.participant_room, name="participant_room"),
    path("<int:pk>/responder/", views.submit_answer, name="submit_answer"),
    path("<int:pk>/resultados/", views.game_results, name="results"),
]
