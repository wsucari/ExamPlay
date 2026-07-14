# ExamPlay

ExamPlay es una aplicación educativa de cuestionarios y partidas en vivo construida con Django. Un docente crea preguntas, abre una sala con PIN y controla el avance; los estudiantes ingresan desde el navegador sin crear cuenta, responden una vez y ven resultados y clasificación en tiempo real.

## Funcionalidades

- Registro, inicio de sesión, cierre mediante POST y panel privado para docentes.
- Cuestionarios propios con alta, detalle, edición, eliminación, activación y conteo de preguntas.
- Preguntas reordenables con imagen opcional, 5–300 segundos y 100–5000 puntos.
- Cinco tipos de pregunta: opción múltiple, verdadero/falso, respuesta corta, ordenamiento y relación de columnas.
- Partidas con PIN único de seis dígitos y estados: espera, pregunta, resultados y finalizada.
- Participantes invitados con apodo único, avatar obligatorio y acceso vinculado a la sesión del navegador.
- Preguntas, respuestas, resultados, ranking parcial y final sincronizados mediante WebSockets.
- Historial de partidas y detalle de respuestas por participante.
- Administración Django configurada para cuestionarios, preguntas, avatares, partidas, participantes y respuestas.
- SQLite e InMemory Channel Layer en desarrollo; PostgreSQL y Redis configurables por variables.

## Arquitectura

- `accounts`: autenticación y panel del docente.
- `quizzes`: cuestionarios, preguntas, alternativas, formularios y permisos de propietario.
- `livegames`: partidas, participantes, respuestas, transiciones y consumidores WebSocket.
- `core`: página de inicio.
- `config`: settings, URLs y entradas ASGI/WSGI.
- `templates` y `static`: Bootstrap 5, CSS propio y JavaScript nativo.

La aplicación sirve HTTP y WebSockets mediante ASGI. Cada partida usa el grupo Channels `game_<id>`. El consumidor docente exige usuario autenticado y propietario; el consumidor participante exige una sesión registrada en esa partida. En desarrollo, no se necesita Redis si se ejecuta un solo proceso.

### Tipos de pregunta

- **Opción múltiple:** exactamente cuatro alternativas y una o más correctas. El participante debe seleccionar exactamente todo el conjunto correcto; no hay puntaje parcial.
- **Verdadero o falso:** dos opciones fijas y una correcta.
- **Respuesta corta:** entre una y diez respuestas válidas. Por defecto se ignoran mayúsculas, tildes y espacios repetidos; el docente puede activar distinción de mayúsculas.
- **Modo proyección:** el docente puede ocultar o revelar desde la sala en vivo las soluciones, estadísticas y clasificaciones. La preferencia se conserva por partida y no altera los resultados individuales que reciben los participantes.
- **Revelación de respuestas:** mientras una pregunta está activa no se muestran soluciones en la pantalla docente. Al responder todos los participantes o agotarse el tiempo se publican los resultados automáticamente; el docente también conserva el control manual.
- **Ordenamiento:** entre dos y diez elementos. El orden registrado por el docente es la secuencia correcta y los estudiantes los reciben mezclados.
- **Relacionar columnas:** entre dos y diez parejas únicas. Cada elemento derecho solo puede utilizarse una vez.

`AnswerOption` funciona como componente de pregunta: alternativa, respuesta textual válida, elemento ordenable o pareja, según `Question.question_type`. `ParticipantAnswer` conserva una alternativa opcional, texto libre y un `JSONField` para respuestas estructuradas. Esta separación permite añadir evaluadores futuros sin cambiar el flujo de partidas ni confiar en el navegador.

`Avatar` mantiene un catálogo administrable por categoría (animales, objetos y personajes genéricos), con símbolo, color e imagen personalizada opcional. La aplicación incluye quince avatares originales iniciales. Los nuevos participantes deben seleccionar uno activo; los registros históricos sin avatar se conservan y muestran una representación neutral.

## Puntaje

El servidor mide el tiempo desde `question_started_at`; no acepta tiempos ni puntos enviados por JavaScript. Una respuesta incorrecta obtiene 0. Una correcta obtiene entre 50 % y 100 % del máximo:

```text
puntos = redondear(puntaje_maximo × (0.5 + 0.5 × (1 - tiempo_usado / tiempo_limite)))
```

El tiempo se limita al intervalo válido. Al inicio se obtiene el 100 %, al agotarse el tiempo el 50 %; después del límite no se acepta la respuesta.
Las preguntas de ordenamiento y relación se califican de forma integral: la secuencia o todas las parejas deben ser correctas. Así se mantiene una regla de puntaje uniforme y fácil de interpretar.

## Requisitos

- Python 3.13 (el proyecto fue verificado con 3.13.1).
- Django 5.2 (verificado con 5.2.16).
- Redis es opcional localmente y necesario para producción con más de un proceso.
- PostgreSQL es recomendado en producción.

## Instalación en Windows

En PowerShell:

```powershell
cd C:\django\ExamPlay
py -3.13 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre `http://127.0.0.1:8000/`. `runserver` es servido por Daphne al estar instalado en primer lugar, por lo que admite WebSockets.

Las variables no se leen automáticamente desde un archivo `.env`. Puedes cargarlas con tu gestor de entorno o en PowerShell, por ejemplo:

```powershell
$env:SECRET_KEY = "clave-local"
$env:DEBUG = "True"
python manage.py runserver
```

## Redis opcional

Sin `REDIS_URL`, ExamPlay usa memoria local. Para probar Redis:

```powershell
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python manage.py runserver
```

El modo en memoria no comparte mensajes entre procesos y no debe usarse para escalar producción.

## Variables de entorno

| Variable | Uso | Ejemplo |
|---|---|---|
| `SECRET_KEY` | Obligatoria con `DEBUG=False` | valor aleatorio largo |
| `DEBUG` | Activa modo desarrollo | `True` o `False` |
| `ALLOWED_HOSTS` | Hosts separados por coma | `examplay.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS separados por coma | `https://examplay.onrender.com` |
| `DATABASE_URL` | PostgreSQL; vacía usa SQLite | `postgresql://...` |
| `REDIS_URL` | Capa Channels Redis; vacía usa memoria | `redis://...` |
| `SECURE_SSL_REDIRECT` | Fuerza HTTPS cuando no está en debug | `True` |
| `SECURE_HSTS_SECONDS` | Duración de HSTS en producción | `31536000` |

Consulta `.env.example`; nunca confirmes `.env` ni credenciales.

## Pruebas y controles

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

Las pruebas cubren correo duplicado, logout POST, aislamiento entre docentes, reglas de cada tipo de pregunta, PIN, fórmula de puntaje, límite de tiempo, respuesta única y acceso del participante por sesión.

## Preparación para Render

El repositorio incluye `render.yaml`, `build.sh` y `Procfile`.

1. Crea externamente una base PostgreSQL y un Redis en Render.
2. Configura `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.
3. Usa `bash build.sh` como comando de construcción.
4. Usa `daphne -b 0.0.0.0 -p $PORT config.asgi:application` como comando de inicio.

El build instala dependencias, ejecuta `collectstatic` y aplica migraciones. `gunicorn` también está incluido para despliegues exclusivamente WSGI, pero Daphne es el comando indicado aquí porque ExamPlay necesita WebSockets. Las imágenes en el disco efímero de Render no son persistentes: para uso real configura posteriormente un almacenamiento de objetos compatible con Django.

## Estructura

```text
ExamPlay/
├── accounts/          # autenticación
├── core/              # inicio
├── quizzes/           # cuestionarios y preguntas
├── livegames/         # partidas y WebSockets
├── config/            # configuración ASGI/WSGI
├── templates/         # vistas HTML
├── static/            # CSS y JavaScript
├── manage.py
├── requirements.txt
├── build.sh
└── render.yaml
```

## Flujo de uso

1. El docente se registra, crea un cuestionario y agrega preguntas válidas.
2. Desde “Nueva partida” elige el cuestionario y obtiene un PIN.
3. Cada estudiante abre “Ingresar con PIN”, escribe PIN y apodo, y espera.
4. El docente inicia, publica una pregunta a la vez, muestra resultados y avanza.
5. Al finalizar, todos ven el ranking; el docente conserva el detalle en el historial.

El superusuario administra todos los registros desde `/admin/`; los docentes normales solo acceden mediante las vistas filtradas por propietario.
