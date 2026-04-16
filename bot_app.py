
import os
import json
import base64
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from dotenv import load_dotenv
from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    raise RuntimeError(".env файл не найден")

bot = Bot(token=os.getenv("TELEGRAM_API_KEY"))
dp = Dispatcher()

secret_key = base64.urlsafe_b64decode(os.getenv("SESSION_SECRET").encode())
storage = EncryptedCookieStorage(secret_key)
middleware = session_middleware(storage)

app = web.Application(middlewares=[middleware])
setup(app, storage)

async def index(request):
    return web.FileResponse('./html_dir/bot_app.html')

async def init_session(request):
    session = await get_session(request)
    user_id = request.query.get('user_id')
    username = request.query.get('username')

    if user_id and username:
        session['user_id'] = user_id
        session['username'] = username
        user_id = int(user_id)
        session['score'] = db.get_score(user_id)

    return web.HTTPFound(f'/html_dir/quiz.html?user_id={user_id}&username={username}')

from urllib.parse import urlencode

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    try:
        user = message.from_user
        db.get_or_create_user(user.id, user.first_name)

        web_app_url = os.getenv("WEB_APP_URL")
        if not web_app_url:
            await message.answer("Ошибка: WEB_APP_URL не задан")
            return

        query_params = urlencode({
            "user_id": user.id,
            "username": user.first_name
        })
        full_url = f"{web_app_url}?{query_params}"

        kb = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Начать обучение", web_app=types.WebAppInfo(url=full_url))]],
            resize_keyboard=True
        )

        await message.answer(
            f"""Привет, {user.first_name}! 👋
Ты на шаг ближе к тому, чтобы распознавать рыночные манипуляции как профи!

📈 Что делает бот?
Мы научим тебя выявлять самые популярные схемы:
– Spoofing,  
– Pump & Dump,  
– Front-running,  
– и другие.

🤖 Как это работает?

Перейди в раздел «Обучение», чтобы изучить стратегии манипуляций на графиках.

Пройди мини-квиз и проверь, насколько ты внимателен.

Загляни в «Умного инвестора», где ты сможешь соревноваться с другими и зарабатывать баллы за правильные ответы.

🧠 Зачем это нужно?
– Повысишь финансовую грамотность  
– Узнаешь, как защитить себя от манипуляций  
– Поможешь сделать рынок прозрачнее

💡 Всё, что нужно — это внимание и желание учиться.
Готов? Тогда поехали!""",
            reply_markup=kb
        )

    except Exception as e:
        print("Ошибка в start_cmd:", e)
        await message.answer("Произошла внутренняя ошибка.")



async def api_check_user(request):
    session = await get_session(request)
    if not session.get('user_id'):
        return web.json_response({
            'error': 'Unauthorized',
            'user_id': None,
            'username': None,
            'score': 0,
            'limit_reached': True,
            'remaining_attempts': 0
        }, status=200)

    user_id = session['user_id']
    username = session['username']
    db.get_or_create_user(user_id, username)
    can_request = db.can_user_request(user_id)
    score = db.get_score(user_id)

    remaining_attempts = 20 - db.get_user_requests_today(user_id)

    return web.json_response({
        'user_id': user_id,
        'username': username,
        'score': score,
        'limit_reached': can_request,
        'remaining_attempts': remaining_attempts
    })

# Увеличение счётчика правильных ответов
async def api_increment_correct(request):
    data = await request.json()
    name = data.get('name')
    if not name:
        return web.json_response({'error': 'Missing name'}, status=400)

    db.increment_correct(name)
    return web.json_response({'status': 'correct incremented'})

# Увеличение счётчика неправильных ответов
async def api_increment_wrong(request):
    data = await request.json()
    name = data.get('name')
    if not name:
        return web.json_response({'error': 'Missing name'}, status=400)

    db.increment_wrong(name)
    return web.json_response({'status': 'wrong incremented'})

# Получение статистики по имени
async def api_get_answer_stats(request):
    name = request.query.get('name')
    if not name:
        return web.json_response({'error': 'Missing name'}, status=400)

    stats = db.get_stats(name)
    return web.json_response({'name': name, **stats})

# Получение ответа и обновление очков
async def api_submit_answer(request):
    session = await get_session(request)
    if not session.get('user_id'):
        return web.json_response({'error': 'Unauthorized'}, status=401)

    data = await request.json()
    user_id = session['user_id']
    correct = data.get('correct')
    name = data.get('name')  # Добавлено

    if not name:
        return web.json_response({'error': 'Strategy name is missing'}, status=400)

    db.register_user_request(user_id)

    if not db.can_user_request(user_id):
        return web.json_response({'error': 'Лимит попыток исчерпан'}, status=403)

    # Обновляем статистику по стратегии
    if correct:
        db.increment_correct(name)
    else:
        db.increment_wrong(name)

    # Обновляем счёт
    delta = 5 if correct else -5
    db.update_score(user_id, delta)
    session['score'] = db.get_score(user_id)

    return web.json_response({'new_score': session['score']})


# bot_app.py
async def api_use_attempt(request):
    session = await get_session(request)
    if not session.get('user_id'):
        return web.json_response({'error': 'Unauthorized'}, status=401)

    user_id = int(session['user_id'])

    if not db.can_user_request(user_id):
        return web.json_response({'error': 'Лимит попыток исчерпан'}, status=403)
    remaining = 20 - db.get_user_requests_today(user_id)

    return web.json_response({'ok': True, 'remaining_attempts': remaining})

# bot_app.py (изменения)
async def api_get_rating(request):
    session = await get_session(request)
    if not session.get('user_id'):
        return web.json_response({'error': 'Unauthorized'}, status=401)

    user_id = int(session['user_id'])
    top_players = db.get_top_players(3)
    full_rating = db.get_full_rating()

    # Находим позицию и счет пользователя
    user_position = next(
        (i + 1 for i, user in enumerate(full_rating) if user['id'] == user_id),
        len(full_rating) + 1
    )
    user_score = next(
        (user['score'] for user in full_rating if user['id'] == user_id),
        0
    )

    # Получаем ближайших конкурентов
    nearby_players = []
    if user_position > 3:
        start_idx = max(0, user_position - 3)
        end_idx = min(len(full_rating), user_position + 2)
        nearby_players = full_rating[start_idx:end_idx]

    return web.json_response({
        'top_players': top_players,
        'user_position': user_position,
        'user_score': user_score,
        'nearby_players': nearby_players  # Добавляем ближайших конкурентов
    })
async def api_get_top_strategies(request):
    strategies = db.get_top_strategies()
    return web.json_response(strategies)


async def serve_list_json(request):
    json_path = os.path.join(questions_path, "list.json")
    if not os.path.exists(json_path):
        return web.json_response({'error': 'Файл list.json не найден'}, status=404)

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    return web.json_response(data)


# ==== РОУТИНГ ====

questions_path = os.path  .join(BASE_DIR, "questions")
app.router.add_get('/questions/list.json', serve_list_json)
app.router.add_get('/api/get_rating', api_get_rating)
app.router.add_get('/', index)
app.router.add_get('/init_session', init_session)
app.router.add_post('/api/check_user', api_check_user)
app.router.add_post('/api/submit_answer', api_submit_answer)
app.router.add_static('/html_dir/', path=os.path.join(BASE_DIR, 'html_dir'))
app.router.add_static('/questions/', path=questions_path)
app.router.add_post('/api/use_attempt', api_use_attempt)
app.router.add_post('/api/answers/correct', api_increment_correct)
app.router.add_post('/api/answers/wrong', api_increment_wrong)
app.router.add_get('/api/answers/stats', api_get_answer_stats)
app.router.add_get('/api/answers/top', api_get_top_strategies)


# Старт aiogram
async def on_startup(app):
    import asyncio
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

app.on_startup.append(on_startup)


import db
if __name__ == '__main__':
    print("🔧 Инициализация БД...")
    db.init_db()
    print("🚀 Запуск aiohttp приложения...")
    web.run_app(app, host='0.0.0.0', port=5000)

