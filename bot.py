import re
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь стандартных единиц времени (в минутах)
time_units = {
    'минута': 1, 'минуты': 1, 'минут': 1, 'минуту': 1, 'мин': 1,
    'час': 60, 'часа': 60, 'часов': 60, 'часу': 60, 'ч': 60,
    'день': 1440, 'дня': 1440, 'дней': 1440, 'дню': 1440,
    'сутки': 1440, 'суток': 1440,
    'неделя': 10080, 'недели': 10080, 'недель': 10080, 'неделю': 10080, 
    'секунд': 1/60, 'секунды': 1/60, 'секунда': 1/60, 'секунду': 1/60,
    'год': 525600, 'года': 525600, 'лет': 525600,
}

# Словарь для пользовательских единиц (хранится в памяти)
user_units = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
🤖 Бот-напоминатель

Просто отправьте время, через которое нужно напомнить, например:
• 30 минут
• 1 час  
• 2 часа
• 15 минут
• 1/2 минуты
• 1/4 часа
• 0.5 часа

💡 Можно добавить текст напоминания:
• 30 минут позвонить маме
• 1 час приготовить ужин
• 2 часа заняться спортом

📋 Доступные команды:
/start - показать это сообщение
/addunit [название] [минуты] - добавить свою единицу времени
/myunits - показать мои единицы времени

Пример добавления единицы:
/addunit пара 90
/addunit перемена 15
/addunit сессия 45
    """
    await update.message.reply_text(welcome_text)

async def add_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление пользовательской единицы времени"""
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /addunit [название] [минуты]\n\n"
            "Примеры:\n"
            "/addunit пара 90\n"
            "/addunit перемена 15\n"
            "/addunit сессия 45\n\n"
            "После добавления можно использовать:\n"
            "• 1 пара = 90 минут\n"
            "• 2 пары = 180 минут"
        )
        return
    
    try:
        unit_name = context.args[0].lower()
        multiplier = float(context.args[1])
        
        if multiplier <= 0:
            await update.message.reply_text("❌ Множитель должен быть положительным числом")
            return
        
        # Проверяем, не существует ли уже такая единица
        if unit_name in time_units:
            await update.message.reply_text(f"❌ Единица '{unit_name}' уже существует в стандартных")
            return
        
        # Инициализируем словарь для пользователя, если его нет
        if user_id not in user_units:
            user_units[user_id] = {}
        
        # Добавляем единицу
        user_units[user_id][unit_name] = multiplier
        
        await update.message.reply_text(
            f"✅ Единица '{unit_name}' добавлена!\n"
            f"1 {unit_name} = {multiplier} минут\n\n"
            f"Теперь можно использовать:\n"
            f"• 1 {unit_name}\n"
            f"• 2 {unit_name}\n"
            f"• 1/2 {unit_name}\n"
            f"• 0.5 {unit_name}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Множитель должен быть числом")

async def my_units(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать пользовательские единицы времени"""
    user_id = update.effective_user.id
    
    if user_id not in user_units or not user_units[user_id]:
        await update.message.reply_text(
            "📝 У вас пока нет своих единиц времени.\n\n"
            "Добавьте их командой:\n"
            "/addunit [название] [минуты]\n\n"
            "Пример:\n"
            "/addunit пара 90"
        )
        return
    
    units_text = "📝 Ваши единицы времени:\n\n"
    for unit_name, multiplier in user_units[user_id].items():
        units_text += f"• {unit_name} = {multiplier} минут\n"
    
    units_text += "\nИспользуйте их в сообщениях:\n"
    for unit_name in user_units[user_id].keys():
        units_text += f"• 1 {unit_name}\n"
        units_text += f"• 2 {unit_name}\n"
    
    await update.message.reply_text(units_text)

async def send_reminder(context):
    """Функция для отправки напоминания"""
    job = context.job
    reminder_text = job.data.get('reminder_text', '')
    
    if reminder_text:
        message = f"⏰ Время вышло!\n📝 Напоминание: {reminder_text}"
    else:
        message = "⏰ Время вышло!"
    
    await context.bot.send_message(job.chat_id, text=message)

def parse_time_and_text(text: str, user_id: int):
    """
    Парсит сообщение и возвращает время в минутах и текст напоминания
    """
    original_text = text
    text_lower = text.lower().strip()
    logger.info(f"Парсим текст: '{text_lower}'")
    
    # Собираем все доступные единицы для пользователя
    all_units = {**time_units}
    if user_id in user_units:
        all_units.update(user_units[user_id])
    
    # Сортируем единицы по длине (от самых длинных к коротким)
    # чтобы сначала находить полные совпадения
    sorted_units = sorted(all_units.items(), key=lambda x: len(x[0]), reverse=True)
    
    # Сначала ищем дроби с единицами измерения
    for unit_name, multiplier in sorted_units:
        # Используем границы слов чтобы избежать частичных совпадений
        fraction_pattern = rf'(\d+)/(\d+)\s+{re.escape(unit_name)}\b'
        match = re.search(fraction_pattern, text_lower)
        if match:
            try:
                numerator = float(match.group(1))
                denominator = float(match.group(2))
                if denominator != 0:
                    number = numerator / denominator
                    result = number * multiplier
                    
                    # Находим позицию конца найденного времени в оригинальном тексте
                    time_part = match.group(0)
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # Извлекаем текст напоминания (все что после времени)
                    reminder_text = original_text[end_pos:].strip()
                    
                    logger.info(f"Найдена дробь: {numerator}/{denominator} {unit_name} = {result} минут, текст: '{reminder_text}'")
                    return result, reminder_text
            except (ValueError, ZeroDivisionError):
                continue
    
    # Затем ищем обычные числа с единицами измерения
    for unit_name, multiplier in sorted_units:
        # Используем границы слов
        number_pattern = rf'(\d+\.\d+|\d+)\s+{re.escape(unit_name)}\b'
        match = re.search(number_pattern, text_lower)
        if match:
            try:
                number = float(match.group(1))
                result = number * multiplier
                
                # Находим позицию конца найденного времени в оригинальном тексте
                start_pos = match.start()
                end_pos = match.end()
                
                # Извлекаем текст напоминания (все что после времени)
                reminder_text = original_text[end_pos:].strip()
                
                logger.info(f"Найдено число: {number} {unit_name} = {result} минут, текст: '{reminder_text}'")
                return result, reminder_text
            except ValueError:
                continue
    
    logger.warning("Не удалось распознать время")
    return None, ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    
    logger.info(f"Получено сообщение от {user_id}: '{text}'")
    
    # Парсим время и текст
    minutes, reminder_text = parse_time_and_text(text, user_id)
    
    if minutes is None:
        # Показываем доступные единицы в ошибке
        available_units = "• минуты\n• часы\n• дни\n• недели\n• секунды"
        if user_id in user_units:
            available_units += "\n• " + "\n• ".join(user_units[user_id].keys())
        
        await update.message.reply_text(
            f"❌ Не удалось распознать время.\n\n"
            f"Доступные единицы:\n{available_units}\n\n"
            f"Примеры:\n"
            f"• 30 минут\n"
            f"• 1 час\n"
            f"• 1/2 часа\n"
            f"• 0.5 часа\n"
            f"• 10 секунд\n\n"
            f"💡 Можно добавить текст:\n"
            f"• 30 минут позвонить маме\n"
            f"• 1 час приготовить ужин\n"
            f"• 10 секунд продолжить работу"
        )
        return
    
    logger.info(f"Распознано время: {minutes} минут, текст: '{reminder_text}'")
    
    # Проверяем что время положительное
    if minutes <= 0:
        await update.message.reply_text("❌ Время должно быть положительным")
        return
    
    # Преобразуем в секунды
    seconds = int(minutes * 60)
    logger.info(f"Установка таймера на {seconds} секунд ({minutes} минут)")
    
    try:
        # Устанавливаем таймер с данными напоминания
        context.job_queue.run_once(
            callback=send_reminder,
            when=seconds,
            chat_id=update.effective_chat.id,
            data={'reminder_text': reminder_text}  # Передаем текст напоминания
        )
        
        logger.info("Таймер успешно установлен!")
        
        # Формируем сообщение подтверждения
        if minutes < 1:
            seconds_total = int(minutes * 60)
            time_display = f"{seconds_total} секунд"
        elif minutes < 60:
            if minutes == int(minutes):
                time_display = f"{int(minutes)} минут"
            else:
                time_display = f"{minutes:.1f} минут"
        else:
            hours = minutes / 60
            if hours == int(hours):
                time_display = f"{int(hours)} часов"
            else:
                time_display = f"{hours:.1f} часов"
        
        # Сообщение подтверждения
        if reminder_text:
            confirmation_message = f"✅ Напоминание установлено на {time_display}\n📝 Текст: {reminder_text}"
        else:
            confirmation_message = f"✅ Напоминание установлено на {time_display}"
        
        await update.message.reply_text(confirmation_message)
        
    except Exception as e:
        logger.error(f"Ошибка при установке таймера: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при установке таймера")

def main():
    """Основная функция"""
    TOKEN = "8259277645:AAG6Mj32b_kQ0xkKyZjJvuiGz1IvFGwfFec"
    
    logger.info("Запуск бота...")
    
    try:
        application = Application.builder().token(TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("addunit", add_unit))
        application.add_handler(CommandHandler("myunits", my_units))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Бот запущен и готов к работе...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    main()  