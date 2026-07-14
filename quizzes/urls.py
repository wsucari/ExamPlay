from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    path(
        "",
        views.quiz_list,
        name="list",
    ),
    path(
        "crear/",
        views.quiz_create,
        name="create",
    ),
    path(
        "<int:pk>/",
        views.quiz_detail,
        name="detail",
    ),
    path(
        "<int:pk>/editar/",
        views.quiz_update,
        name="update",
    ),
    path(
        "<int:pk>/eliminar/",
        views.quiz_delete,
        name="delete",
    ),
    
]