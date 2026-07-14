from django.db import migrations


AVATARS = (
    ("Zorro solar", "zorro-solar", "animal", "🦊", "#EA580C", 10),
    ("Búho cósmico", "buho-cosmico", "animal", "🦉", "#4338CA", 20),
    ("Panda pixel", "panda-pixel", "animal", "🐼", "#334155", 30),
    ("Ajolote aqua", "ajolote-aqua", "animal", "🦎", "#0891B2", 40),
    ("Conejo veloz", "conejo-veloz", "animal", "🐰", "#DB2777", 50),
    ("Cohete naranja", "cohete-naranja", "object", "🚀", "#C2410C", 10),
    ("Brújula sabia", "brujula-sabia", "object", "🧭", "#0F766E", 20),
    ("Bombilla brillante", "bombilla-brillante", "object", "💡", "#CA8A04", 30),
    ("Planeta violeta", "planeta-violeta", "object", "🪐", "#7E22CE", 40),
    ("Cubo creativo", "cubo-creativo", "object", "🧊", "#0284C7", 50),
    ("Explorador estelar", "explorador-estelar", "character", "🧑‍🚀", "#1D4ED8", 10),
    ("Mente científica", "mente-cientifica", "character", "🧑‍🔬", "#047857", 20),
    ("Artista arcoíris", "artista-arcoiris", "character", "🧑‍🎨", "#BE185D", 30),
    ("Guardián amable", "guardian-amable", "character", "🦸", "#6D28D9", 40),
    ("Aventurera valiente", "aventurera-valiente", "character", "🧗", "#B45309", 50),
)


def create_avatars(apps, schema_editor):
    Avatar = apps.get_model("livegames", "Avatar")
    for name, slug, category, symbol, color, order in AVATARS:
        Avatar.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "category": category,
                "symbol": symbol,
                "background_color": color,
                "is_active": True,
                "order": order,
            },
        )


def remove_avatars(apps, schema_editor):
    Avatar = apps.get_model("livegames", "Avatar")
    Participant = apps.get_model("livegames", "Participant")
    avatars = Avatar.objects.filter(slug__in=[item[1] for item in AVATARS])
    Participant.objects.filter(avatar__in=avatars).update(avatar=None)
    avatars.delete()


class Migration(migrations.Migration):
    dependencies = [("livegames", "0004_avatar_participant_avatar")]

    operations = [migrations.RunPython(create_avatars, remove_avatars)]
