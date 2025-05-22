import os
import logging
from dotenv import load_dotenv
import json

# Загрузка переменных окружения из .env файла
load_dotenv()

# Конфигурационные параметры
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID", 0))

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файл для сохранения соответствий пользователь ↔ тема
USER_TOPIC_FILE = "user_topic_mapping.json"

# Функции для работы с соответствиями пользователь ↔ тема
def save_user_topic_mapping(mapping):
    """Сохраняет соответствия пользователь ↔ тема в файл"""
    try:
        with open(USER_TOPIC_FILE, 'w') as f:
            json.dump(mapping, f)
    except Exception as e:
        logger.error(f"Error saving user-topic mapping: {e}")

def load_user_topic_mapping():
    """Загружает соответствия пользователь ↔ тема из файла"""
    try:
        if os.path.exists(USER_TOPIC_FILE):
            with open(USER_TOPIC_FILE, 'r') as f:
                mapping = json.load(f)
                # Конвертируем строковые ключи обратно в int
                return {int(user_id): topic_id for user_id, topic_id in mapping.items()}
        return {}
    except Exception as e:
        logger.error(f"Error loading user-topic mapping: {e}")
        return {}