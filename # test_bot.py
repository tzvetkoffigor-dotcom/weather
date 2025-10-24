# test_bot.py
import asyncio
from telegram import Bot

async def test_bot():
    TOKEN = "8259277645:AAG6Mj32b_kQ0xkKyZjJvuiGz1IvFGwfFecEN"  # Ваш токен
    try:
        bot = Bot(token=TOKEN)
        me = await bot.get_me()
        print(f"✅ Бот работает: {me.first_name} (@{me.username})")
        
        # Тест отправки сообщения
        # await bot.send_message(chat_id=YOUR_CHAT_ID, text="Тестовое сообщение")
        # print("✅ Сообщение отправлено")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_bot()) 