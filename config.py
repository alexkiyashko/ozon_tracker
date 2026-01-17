"""
Конфигурация OZON Price Tracker
"""

import os

# ============= ОСНОВНЫЕ НАСТРОЙКИ =============

# Токен Telegram бота (получите у @BotFather)
BOT_TOKEN = "8564510707:AAHMnir2-66R5-NqPM0nr7vgBm2uLfUL17A"

# ============= БАЗА ДАННЫХ =============

DATABASE_PATH = "ozon_tracker.db"

# ============= МОНИТОРИНГ =============

# Интервал проверки цен (секунды) - 10 минут
CHECK_INTERVAL = 600

# Максимум товаров на пользователя
MAX_PRODUCTS_PER_USER = 15

# ============= ПАРСЕР =============

# Headless режим (True для сервера)
HEADLESS_MODE = True

# Таймаут загрузки страницы (секунды)
PARSER_TIMEOUT = 30

# Задержка между запросами (секунды)
PARSER_DELAY = 2

# Задержка после загрузки страницы (секунды)
PAGE_LOAD_DELAY = 5

# ============= ПУТИ =============

# Базовая директория для данных
RUNTIME_DIR = os.path.expanduser("~/ozon_runtime")

# Путь к файлу прокси
PROXY_STORAGE_PATH = os.path.join(RUNTIME_DIR, "proxies.txt")

# Путь для кэша matplotlib
MPLCONFIGDIR = os.path.join(RUNTIME_DIR, "mpl")

# Создаем директории
os.makedirs(RUNTIME_DIR, exist_ok=True)
os.makedirs(MPLCONFIGDIR, exist_ok=True)

# ============= ГРАФИКИ =============

CHART_SIZE = (12, 6)
CHART_DPI = 100
MAX_CHART_RECORDS = 100

# ============= ЛОГИРОВАНИЕ =============

LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
