import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from aiohttp import web
from aiohttp_session import get_session, session_middleware, setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

import db

BASE_DIR = Path(__file__).resolve().parent
CONTENT_PATH = BASE_DIR / "content" / "moscow_xx_century.json"
PHOTO_LIBRARY_PATH = BASE_DIR / "content" / "photo_library.json"
STATIC_DIR = BASE_DIR / "html_dir"
STATIC_ASSETS_DIR = STATIC_DIR / "static"


def load_content() -> Dict[str, Any]:
    with CONTENT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_photo_library() -> Dict[str, Any]:
    if not PHOTO_LIBRARY_PATH.exists():
        return {"notes": "", "objects": {}}

    with PHOTO_LIBRARY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "objects" not in data or not isinstance(data["objects"], dict):
        data["objects"] = {}
    return data


CONTENT = load_content()
PHOTO_LIBRARY = load_photo_library()
QUESTIONS = {item["id"]: item for item in CONTENT["quiz"]}


def get_secret_key() -> bytes:
    raw = os.getenv("SESSION_SECRET")
    if raw:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass

    # Safe fallback for local development only.
    return b"0123456789abcdef0123456789abcdef"


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def render_markdown_report(user: Dict[str, Any]) -> str:
    timeline_lines = [
        f"- **{item['period']}**: {item['label']} ({item['focus']})" for item in CONTENT["timeline"]
    ]

    route_lines = []
    for stop in CONTENT["route_stops"]:
        route_lines.append(f"## {stop['title']}")
        route_lines.append(f"**Период:** {stop['period']}")
        route_lines.append(f"**Ключевая идея:** {stop['key_message']}")
        route_lines.append("")
        route_lines.append("### Объекты")
        for obj in stop["objects"]:
            route_lines.append(
                "- "
                + f"**{obj['name']}** ({obj['years']}); "
                + f"архитекторы/авторы: {obj['architects']}; "
                + f"заказчик: {obj['customers']}; "
                + f"статус: {obj['status']}."
            )
            route_lines.append(f"  - Факт: {obj['fact']}")
        route_lines.append("")

    unrealized_lines = [
        f"- **{item['name']}** ({item['period']}): {item['why_important']}"
        for item in CONTENT["unrealized_projects"]
    ]

    influence_lines = [
        f"- {item['thesis']}" for item in CONTENT["european_influences"]
    ]

    social_lines = [f"- {line}" for line in CONTENT["social_impact"]]
    source_lines = [
        f"- [{source['title']}]({source['url']})"
        for source in CONTENT["sources"].values()
    ]
    photo_lines = []
    photos = PHOTO_LIBRARY.get("objects", {})
    for stop in CONTENT["route_stops"]:
        for obj in stop["objects"]:
            photo_meta = photos.get(obj["name"], {})
            if not photo_meta:
                continue
            if not photo_meta.get("filename"):
                continue

            details = [f"файл: `html_dir/static/photos/{photo_meta['filename']}`"]
            if photo_meta.get("credit"):
                details.append(f"автор: {photo_meta['credit']}")
            if photo_meta.get("license"):
                details.append(f"лицензия: {photo_meta['license']}")
            if photo_meta.get("source_url"):
                details.append(f"источник: {photo_meta['source_url']}")

            photo_lines.append(f"- **{obj['name']}** — " + "; ".join(details))

    md = "\n".join(
        [
            f"# {CONTENT['project']['title']}",
            "",
            f"**Тема:** {CONTENT['project']['theme']}",
            f"**Формат:** {CONTENT['project']['format']}",
            f"**Команда:** {', '.join(CONTENT['project']['team'])}",
            "",
            "## Цель проекта",
            CONTENT["project"]["goal"],
            "",
            "## Состояние ученика",
            f"- Пользователь: {user['username']}",
            f"- Баллы за квиз: {user['score']}",
            f"- Отвечено вопросов: {user['answered_total']}",
            f"- Правильных ответов: {user['correct_total']}",
            "",
            "## Логика экскурсии",
            *timeline_lines,
            "",
            "## Сценарий пешеходной экскурсии",
            *route_lines,
            "## Нереализованные проекты",
            *unrealized_lines,
            "",
            "## Европейские влияния",
            *influence_lines,
            "",
            "## Социальные и культурные последствия",
            *social_lines,
            "",
            "## Вывод",
            "Архитектура Москвы XX века прошла путь от авангардного эксперимента к монументальной репрезентации и затем к индустриальной массовости. Следы всех этапов видны в городской ткани Москвы сегодня.",
            "",
            "## Фотоматериалы (локальная база)",
            *(photo_lines if photo_lines else ["- Добавьте файлы в `html_dir/static/photos/` и заполните `content/photo_library.json`."]),
            "",
            "## Источники",
            *source_lines,
            "",
        ]
    )
    return md


def render_html_report(markdown: str) -> str:
    # Minimal markdown-like rendering for printable output.
    lines = markdown.splitlines()
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("<p class='spacer'></p>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("- "):
            html_lines.append(f"<li>{stripped[2:]}</li>")
        else:
            html_lines.append(f"<p>{stripped}</p>")

    html = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{CONTENT['project']['title']} - Отчет</title>
  <style>
    body {{
      font-family: Georgia, 'Times New Roman', serif;
      line-height: 1.5;
      margin: 24px;
      color: #222;
    }}
    h1 {{ font-size: 28px; margin: 20px 0 8px; }}
    h2 {{ font-size: 20px; margin: 16px 0 8px; }}
    p {{ margin: 6px 0; }}
    li {{ margin: 4px 0 4px 18px; }}
    .spacer {{ margin: 10px 0; }}
    @media print {{
      @page {{ size: A4; margin: 14mm; }}
      body {{ margin: 0; }}
    }}
  </style>
</head>
<body>
{''.join(html_lines)}
</body>
</html>
""".strip()
    return html


async def index(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC_DIR / "index.html")


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def api_init_session(request: web.Request) -> web.Response:
    session = await get_session(request)
    data = await request.json()

    user_id_raw = data.get("user_id")
    username = (data.get("username") or "Гость").strip()[:64]

    if user_id_raw is None:
        return web.json_response({"error": "user_id is required"}, status=400)

    try:
        user_id = int(user_id_raw)
    except (ValueError, TypeError):
        return web.json_response({"error": "user_id must be integer"}, status=400)

    session["user_id"] = user_id
    session["username"] = username
    db.get_or_create_user(user_id, username)

    return web.json_response({"ok": True, "user_id": user_id, "username": username})


async def api_me(request: web.Request) -> web.Response:
    session = await get_session(request)
    user_id = session.get("user_id")
    username = session.get("username")

    if user_id is None:
        return web.json_response(
            {
                "authorized": False,
                "user": None,
                "leaderboard": [],
                "rank": None,
                "answered_question_ids": [],
            }
        )

    db.get_or_create_user(int(user_id), username or "Гость")
    db.touch_user(int(user_id))

    user = db.get_user_summary(int(user_id))
    rank = db.get_user_rank(int(user_id))
    leaderboard = db.get_leaderboard(limit=8)
    answered_question_ids = db.get_answered_question_ids(int(user_id))

    return web.json_response(
        {
            "authorized": True,
            "user": user,
            "rank": rank,
            "leaderboard": leaderboard,
            "answered_question_ids": answered_question_ids,
        }
    )


async def api_content(_: web.Request) -> web.Response:
    payload = dict(CONTENT)
    payload["photo_library"] = PHOTO_LIBRARY.get("objects", {})
    payload["photo_library_notes"] = PHOTO_LIBRARY.get("notes", "")
    return web.json_response(payload)


async def api_submit_answer(request: web.Request) -> web.Response:
    session = await get_session(request)
    user_id = session.get("user_id")

    if user_id is None:
        return web.json_response({"error": "Unauthorized"}, status=401)

    data = await request.json()
    question_id = data.get("question_id")
    selected_option = data.get("selected_option")

    if not question_id or not selected_option:
        return web.json_response({"error": "question_id and selected_option are required"}, status=400)

    question = QUESTIONS.get(question_id)
    if question is None:
        return web.json_response({"error": "Unknown question_id"}, status=404)

    if selected_option not in question["options"]:
        return web.json_response({"error": "selected_option is invalid"}, status=400)

    is_correct = selected_option == question["correct"]
    is_new_answer, new_score = db.record_answer(
        user_id=int(user_id),
        question_id=question_id,
        selected_option=selected_option,
        is_correct=is_correct,
        correct_points=2,
        wrong_points=0,
    )

    return web.json_response(
        {
            "is_correct": is_correct,
            "correct_answer": question["correct"],
            "explanation": question["explanation"],
            "sources": [CONTENT["sources"][sid] for sid in question.get("sources", [])],
            "is_new_answer": is_new_answer,
            "new_score": new_score,
        }
    )


async def api_report_markdown(request: web.Request) -> web.Response:
    session = await get_session(request)
    user_id = session.get("user_id")

    if user_id is None:
        return web.json_response({"error": "Unauthorized"}, status=401)

    user = db.get_user_summary(int(user_id))
    if user is None:
        return web.json_response({"error": "User not found"}, status=404)

    report_md = render_markdown_report(user)
    return web.Response(
        text=report_md,
        headers={"Content-Disposition": "attachment; filename=moscow_excursion_report.md"},
        content_type="text/markdown",
    )


async def api_report_html(request: web.Request) -> web.Response:
    session = await get_session(request)
    user_id = session.get("user_id")

    if user_id is None:
        return web.json_response({"error": "Unauthorized"}, status=401)

    user = db.get_user_summary(int(user_id))
    if user is None:
        return web.json_response({"error": "User not found"}, status=404)

    report_md = render_markdown_report(user)
    report_html = render_html_report(report_md)
    return web.Response(text=report_html, content_type="text/html")


def create_bot_and_dispatcher() -> tuple[Optional[Bot], Dispatcher]:
    token = os.getenv("TELEGRAM_API_KEY")
    dispatcher = Dispatcher()

    if not token:
        return None, dispatcher

    bot = Bot(token=token)

    @dispatcher.message(Command("start"))
    async def start_cmd(message: Message) -> None:
        user = message.from_user
        if user is None:
            await message.answer("Не удалось определить пользователя Telegram.")
            return

        db.get_or_create_user(user.id, user.first_name or "Участник")

        web_app_url = os.getenv("WEB_APP_URL", "http://localhost:8080")
        query_params = urlencode(
            {
                "user_id": user.id,
                "username": user.first_name or "Участник",
            }
        )
        full_url = f"{web_app_url}?{query_params}"

        kb = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(
                        text="Открыть экскурсию по Москве",
                        web_app=WebAppInfo(url=full_url),
                    )
                ]
            ],
            resize_keyboard=True,
        )

        await message.answer(
            "Это учебный исторический бот по теме архитектуры Москвы XX века. "
            "Открой веб-приложение, чтобы пройти экскурсию, квиз и получить материал для PDF/PPT.",
            reply_markup=kb,
        )

    return bot, dispatcher


def create_app() -> web.Application:
    dotenv_path = BASE_DIR / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    db.init_db()

    storage = EncryptedCookieStorage(get_secret_key())
    app = web.Application(middlewares=[session_middleware(storage)])
    setup(app, storage)

    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_post("/api/session/init", api_init_session)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/content", api_content)
    app.router.add_post("/api/quiz/answer", api_submit_answer)
    app.router.add_get("/api/report/markdown", api_report_markdown)
    app.router.add_get("/api/report/html", api_report_html)
    app.router.add_static("/static/", path=STATIC_ASSETS_DIR)

    bot, dispatcher = create_bot_and_dispatcher()
    app["telegram_bot"] = bot

    async def on_startup(_: web.Application) -> None:
        if bot is None:
            print("TELEGRAM_API_KEY не задан. Telegram polling отключен, доступен только WebApp.")
            return

        if get_env_bool("DISABLE_TELEGRAM_POLLING", default=False):
            print("DISABLE_TELEGRAM_POLLING=true. Telegram polling отключен, доступен только WebApp.")
            return

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            app["bot_task"] = app.loop.create_task(dispatcher.start_polling(bot))
        except Exception as exc:
            # Network access may be restricted in local/sandbox runs.
            print(f"Не удалось запустить Telegram polling: {exc}. WebApp продолжит работу без Telegram.")
            try:
                await bot.session.close()
            except Exception:
                pass

    async def on_cleanup(_: web.Application) -> None:
        task = app.get("bot_task")
        if task is not None:
            task.cancel()
        existing_bot = app.get("telegram_bot")
        if existing_bot is not None:
            try:
                await existing_bot.session.close()
            except Exception:
                pass

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == "__main__":
    application = create_app()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    debug = get_env_bool("DEBUG", default=False)
    web.run_app(application, host=host, port=port, print=print if debug else None)
