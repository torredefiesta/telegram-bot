import os
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
import pytz
import aiohttp
import numpy as np

# Flask часть
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is running on Render!'

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Загрузка переменных окружения
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

TOP_LEAGUE_IDS = [
    39, 140, 135, 78, 61, 88, 79, 41, 40, 2, 3, 5, 7, 9, 530, 531
]

def monte_carlo_simulation(home_avg, away_avg, simulations=1000):
    success_count = 0
    for _ in range(simulations):
        home_goals = np.random.poisson(home_avg)
        away_goals = np.random.poisson(away_avg)
        total_goals = home_goals + away_goals
        if total_goals < 2.5:
            success_count += 1
    return success_count / simulations

async def avg_goals_first_half(team_id, session):
    url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {"team": team_id, "last": 5}
    async with session.get(url, headers=headers, params=params) as resp:
        data = await resp.json()
    matches = data.get("response", [])
    total_goals = 0
    count = 0
    for match in matches:
        goals = match.get("goals", {})
        if goals:
            first_half = goals.get("home", 0) // 2 + goals.get("away", 0) // 2
            total_goals += first_half
            count += 1
    return (total_goals / count) if count else 0

async def strategy_1():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {"next": 10, "timezone": "UTC"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
        fixtures = data.get("response", [])

        for fixture in fixtures:
            league_id = fixture["league"]["id"]
            if league_id not in TOP_LEAGUE_IDS:
                continue

            home = fixture["teams"]["home"]
            away = fixture["teams"]["away"]
            match_time = datetime.utcfromtimestamp(fixture["fixture"]["timestamp"])
            local_time = match_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("America/Edmonton"))

            home_avg = await avg_goals_first_half(home["id"], session)
            away_avg = await avg_goals_first_half(away["id"], session)

            probability = monte_carlo_simulation(home_avg, away_avg)

            if probability >= 0.65:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"<b>Стратегия 1 (Монте-Карло):</b> ТМ 2.5 в 1-м тайме\n"
                         f"{home['name']} vs {away['name']}\n"
                         f"Время: {local_time.strftime('%H:%M')}\n"
                         f"Среднее: {home_avg:.2f} / {away_avg:.2f}\n"
                         f"Вероятность ТМ 2.5: {probability:.1%}"
                )

async def run_strategies():
    await strategy_1()

@dp.message(F.text == "/start")
async def start_handler(msg: types.Message):
    await msg.answer("Бот активен. Прогнозы приходят с 6:00 до 16:00 по Калгари.")

@dp.message(F.text == "/predict")
async def predict_handler(msg: types.Message):
    await msg.answer("Ручной запуск анализа...")
    await run_strategies()

async def main():
    print("✅ Бот запущен. Render работает!")
    scheduler = AsyncIOScheduler()
    trigger = CronTrigger(hour="6-16", minute="*/20", timezone="America/Edmonton")
    scheduler.add_job(run_strategies, trigger=trigger)
    scheduler.start()
    await dp.start_polling(bot)

# Запуск Flask и бота параллельно
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_flask).start()
    asyncio.run(main())
