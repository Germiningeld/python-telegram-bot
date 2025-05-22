import asyncio
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.error import TelegramError
import config

# Словарь для хранения соответствий user_id -> topic_id
user_topic_mapping = config.load_user_topic_mapping()


async def setup_commands(application):
    """Настройка меню команд бота"""
    commands = [
        BotCommand("start", "Начать диалог с поддержкой"),
        BotCommand("help", "Инструкция по использованию")
    ]
    await application.bot.set_my_commands(commands)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Здравствуйте! Я бот технической поддержки. Просто отправьте мне ваш вопрос, "
        "и операторы ответят вам как можно скорее."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "Как пользоваться ботом поддержки:\n\n"
        "1. Отправьте ваш вопрос или проблему боту\n"
        "2. Ожидайте ответа от операторов поддержки\n"
        "3. Продолжайте диалог, отвечая на сообщения\n\n"
        "Все ваши сообщения будут обработаны оператором."
    )


async def create_topic_for_user(bot, user_id, first_name, last_name=None):
    """Создает новую тему для пользователя в группе поддержки"""
    try:
        user_name = first_name
        if last_name:
            user_name += f" {last_name}"

        # Создаем тему с именем пользователя и его ID
        topic_name = f"{user_name} (ID: {user_id})"

        result = await bot.create_forum_topic(
            chat_id=config.SUPPORT_GROUP_ID,
            name=topic_name
        )
        topic_id = result.message_thread_id

        # Сохраняем соответствие в память и в файл
        user_topic_mapping[user_id] = topic_id
        config.save_user_topic_mapping(user_topic_mapping)

        config.logger.info(f"Created new topic {topic_id} for user {user_id}")
        return topic_id

    except TelegramError as e:
        config.logger.error(f"Failed to create topic for user {user_id}: {e}")
        return None


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений от пользователей"""
    # Игнорируем сообщения из групп, только личные сообщения
    if update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    message = update.message

    try:
        # Проверяем, есть ли у пользователя тема
        topic_id = user_topic_mapping.get(user_id)

        # Если темы нет, создаем новую
        if not topic_id:
            topic_id = await create_topic_for_user(
                context.bot,
                user_id,
                update.effective_user.first_name,
                update.effective_user.last_name
            )

            if not topic_id:
                config.logger.error(f"Could not create topic for user {user_id}")
                return

        # Пересылаем сообщение в тему поддержки
        await context.bot.copy_message(
            chat_id=config.SUPPORT_GROUP_ID,
            from_chat_id=update.effective_chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )

    except Exception as e:
        config.logger.error(f"Error handling user message: {e}")


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений от операторов в группе поддержки"""
    # Проверяем, что сообщение из супергруппы поддержки и в теме
    if (update.effective_chat.id != config.SUPPORT_GROUP_ID or
            not update.message.is_topic_message):
        return

    # Игнорируем системные сообщения
    if not update.effective_message.text and not update.effective_message.caption:
        if (update.effective_message.document or
                update.effective_message.photo or
                update.effective_message.video or
                update.effective_message.audio or
                update.effective_message.voice or
                update.effective_message.sticker):
            pass  # Это медиа-сообщение, обрабатываем его
        else:
            return  # Это системное сообщение, игнорируем

    # Получаем ID темы
    topic_id = update.message.message_thread_id

    # Находим пользователя, соответствующего этой теме
    user_id = None
    for uid, tid in user_topic_mapping.items():
        if tid == topic_id:
            user_id = uid
            break

    if not user_id:
        config.logger.warning(f"No user found for topic {topic_id}")
        return

    try:
        # Пересылаем сообщение пользователю
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

    except Exception as e:
        config.logger.error(f"Error sending message to user {user_id}: {e}")


def main():
    """Асинхронная версия main()"""
    if not config.TELEGRAM_BOT_TOKEN:
        config.logger.error("No Telegram bot token provided. Please set TELEGRAM_BOT_TOKEN in .env file.")
        return

    if not config.SUPPORT_GROUP_ID:
        config.logger.error("No support group ID provided. Please set SUPPORT_GROUP_ID in .env file.")
        return

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_user_message
    ))

    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO |
         filters.VOICE | filters.Sticker.ALL) & filters.ChatType.PRIVATE,
        handle_user_message
    ))

    application.add_handler(MessageHandler(
        filters.ChatType.SUPERGROUP,
        handle_support_message
    ))

    setup_commands(application)  # Теперь await
    config.logger.info("Starting bot...")
    application.run_polling()  # Запуск с await


if __name__ == "__main__":
    main()