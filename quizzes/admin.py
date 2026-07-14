from django.contrib import admin

from .models import AnswerOption, Question, Quiz


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4
    min_num = 2


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teacher",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "teacher__username",
        "teacher__first_name",
        "teacher__last_name",
    )

    inlines = [
        QuestionInline,
    ]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "short_text",
        "quiz",
        "order",
        "time_limit",
        "points",
    )

    list_filter = (
        "quiz",
        "time_limit",
    )

    search_fields = (
        "text",
        "quiz__title",
    )

    ordering = (
        "quiz",
        "order",
    )

    inlines = [
        AnswerOptionInline,
    ]

    def short_text(self, obj):
        return obj.text[:70]

    short_text.short_description = "Pregunta"


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "question",
        "is_correct",
        "order",
    )

    list_filter = (
        "is_correct",
        "question__quiz",
    )

    search_fields = (
        "text",
        "question__text",
    )