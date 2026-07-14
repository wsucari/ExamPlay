from django.contrib import admin
from django.utils.html import format_html

from .models import Avatar, GameSession, Participant, ParticipantAnswer


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ("preview", "name", "category", "is_active", "order", "participant_count")
    list_editable = ("is_active", "order")
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category", "order", "name")

    @admin.display(description="Vista")
    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" alt="" style="width:42px;height:42px;border-radius:50%;object-fit:cover">', obj.image.url)
        return format_html('<span style="display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:{};font-size:24px">{}</span>', obj.background_color, obj.symbol)

    @admin.display(description="Usos")
    def participant_count(self, obj):
        return obj.participants.count()


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    fields = ("avatar", "nickname", "score", "joined_at")
    readonly_fields = fields
    can_delete = False


class ParticipantAnswerInline(admin.TabularInline):
    model = ParticipantAnswer
    extra = 0
    fields = ("question", "selected_option", "text_answer", "structured_answer", "is_correct", "response_time_ms", "points_earned", "answered_at")
    readonly_fields = fields
    can_delete = False


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("pin", "quiz", "host", "status", "projection_mode", "participant_count", "created_at")
    list_filter = ("status", "projection_mode", "created_at")
    search_fields = ("pin", "quiz__title", "host__username", "host__email")
    readonly_fields = ("pin", "created_at", "started_at", "finished_at", "question_started_at")
    inlines = (ParticipantInline,)

    @admin.display(description="Participantes")
    def participant_count(self, obj):
        return obj.participants.count()


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("nickname", "avatar", "game", "score", "joined_at")
    list_filter = ("avatar__category", "game__status", "joined_at")
    search_fields = ("nickname", "game__pin", "game__quiz__title")
    readonly_fields = ("session_identifier", "score", "joined_at")
    inlines = (ParticipantAnswerInline,)


@admin.register(ParticipantAnswer)
class ParticipantAnswerAdmin(admin.ModelAdmin):
    list_display = ("participant", "question", "is_correct", "points_earned", "answered_at")
    list_filter = ("is_correct", "answered_at", "participant__game")
    search_fields = ("participant__nickname", "question__text", "participant__game__pin")
    readonly_fields = ("participant", "question", "selected_option", "text_answer", "structured_answer", "is_correct", "response_time_ms", "points_earned", "answered_at")
