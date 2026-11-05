import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import BOT_TOKEN, ADMIN_ID, MINI_APP_DOMAIN
from database.db import AsyncSessionLocal, init_db, close_db
from database.models import AppSetting
from sqlalchemy import select
from monitoring.node_alerts import node_alert_loop

logging.basicConfig(level=logging.INFO)

DEFAULT_WELCOME_MESSAGE = (
    "⚡ <b>WELCOME TO ZEUS MONITOR</b>\n\n"
    "🟢 Monitoring system is ready.\n"
    "📊 Open your dashboard using the button below."
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Access denied.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 OPEN ZEUS MONITOR",
                    web_app=WebAppInfo(url=MINI_APP_DOMAIN)
                )
            ]
        ]
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == "welcome_message")
        )
        setting = result.scalar_one_or_none()
        welcome_message = setting.value if setting else DEFAULT_WELCOME_MESSAGE

    await message.answer(
        welcome_message,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    if not ADMIN_ID.isdigit():
        raise RuntimeError("ADMIN_ID is not configured correctly.")

    await init_db()
    monitor_task = asyncio.create_task(node_alert_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
