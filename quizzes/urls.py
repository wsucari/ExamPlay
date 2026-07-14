from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    path("", views.quiz_list, name="list"),
    path("crear/", views.quiz_create, name="create"),
    path("<int:pk>/", views.quiz_detail, name="detail"),
    path("<int:pk>/editar/", views.quiz_update, name="update"),
    path("<int:pk>/eliminar/", views.quiz_delete, name="delete"),
    path("<int:pk>/activar/", views.quiz_toggle, name="toggle"),
    path("<int:quiz_pk>/preguntas/crear/", views.question_create, name="question_create"),
    path("preguntas/<int:pk>/editar/", views.question_update, name="question_update"),
    path("preguntas/<int:pk>/eliminar/", views.question_delete, name="question_delete"),
    path("preguntas/<int:pk>/mover/<str:direction>/", views.question_reorder, name="question_reorder"),
]
