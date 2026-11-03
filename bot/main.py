import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import BOT_TOKEN, ADMIN_ID, MINI_APP_DOMAIN

logging.basicConfig(level=logging.INFO)

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

    await message.answer(
        "⚡ <b>WELCOME TO ZEUS MONITOR</b>\n\n"
        "🟢 Monitoring system is ready.\n"
        "📊 Open your dashboard using the button below.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    if not ADMIN_ID.isdigit():
        raise RuntimeError("ADMIN_ID is not configured correctly.")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
