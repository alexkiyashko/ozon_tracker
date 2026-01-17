"""
Telegram бот для мониторинга цен OZON
"""

import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode

from config import BOT_TOKEN, MAX_PRODUCTS_PER_USER, LOG_LEVEL, LOG_FORMAT, PROXY_STORAGE_PATH
from database import Database
from parser import OzonParser
from chart_generator import ChartGenerator

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database("ozon_tracker.db")
        parser = OzonParser()
chart_gen = ChartGenerator()

# Загрузка прокси
if os.path.exists(PROXY_STORAGE_PATH):
    parser.load_proxies(PROXY_STORAGE_PATH)


def _clean_text(text: str) -> str:
    """Очистка текста от спецсимволов"""
    if not text:
        return ""
    return text.replace("\u00a0", " ").replace("\u200b", "").strip()


def _normalize_proxy(proxy: str) -> str:
    """Нормализация формата прокси"""
    proxy = _clean_text(proxy)
    if not proxy:
        return ""

    # Формат IP:PORT:LOGIN:PASSWORD
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d{2,5}:.+:.+$", proxy):
            return proxy

    # Формат IP:PORT
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d{2,5}$", proxy):
        return proxy

    # socks5:// или http:// URL
    if proxy.startswith(("socks5://", "http://", "https://")):
        return proxy

    return ""


def _load_proxies() -> list:
    """Загрузка списка прокси"""
    if not os.path.exists(PROXY_STORAGE_PATH):
        return []
    try:
        proxies = []
        with open(PROXY_STORAGE_PATH, "r") as f:
            for line in f:
                normalized = _normalize_proxy(line)
                if normalized:
                    proxies.append(normalized)
        return proxies
    except Exception:
        return []


def _save_proxies(proxies: list) -> None:
    """Сохранение списка прокси"""
    os.makedirs(os.path.dirname(PROXY_STORAGE_PATH), exist_ok=True)
    with open(PROXY_STORAGE_PATH, "w") as f:
        f.write("\n".join(proxies) + ("\n" if proxies else ""))
    # Перезагружаем прокси в парсере
    parser.load_proxies(PROXY_STORAGE_PATH)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    await db.add_user(message.from_user.id, message.from_user.username)
    
    welcome_text = """
🤖 <b>OZON Price Tracker</b>

Отслеживаю цены на товары OZON и уведомляю о снижении.

📋 <b>Команды:</b>
/add <ссылка> — Добавить товар
/list — Мои товары
/delete <ID> — Удалить товар
/history <ID> — История цен
/chart <ID> — График цен

🔧 <b>Прокси:</b>
/proxy_add — Добавить прокси
/proxy_list — Список прокси
/proxy_del <№> — Удалить прокси

💡 Добавьте прокси перед добавлением товаров для стабильной работы.
"""
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    help_text = f"""
📖 <b>Справка</b>

<b>/add</b> — Добавить товар
Пример: <code>/add https://www.ozon.ru/product/...</code>

<b>/list</b> — Показать отслеживаемые товары

<b>/delete ID</b> — Удалить товар
Пример: <code>/delete 1</code>

<b>/history ID</b> — История цен товара

<b>/chart ID</b> — График изменения цены

<b>/proxy_add IP:PORT:LOGIN:PASSWORD</b> — Добавить прокси

<b>/proxy_list</b> — Список прокси

<b>/proxy_del №</b> — Удалить прокси по номеру

📊 Лимит товаров: {MAX_PRODUCTS_PER_USER}
⏱ Проверка цен: каждые 10 минут
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@dp.message(Command("add"))
async def cmd_add(message: Message):
    """Команда /add для добавления товара"""
    text = message.text
    url_match = re.search(r'https?://(?:www\.)?ozon\.ru/\S+', text)
    
    proxies = _load_proxies()
    if not proxies:
        await message.answer(
            "⚠️ Добавьте прокси для стабильной работы:\n"
            "<code>/proxy_add IP:PORT:LOGIN:PASSWORD</code>",
            parse_mode=ParseMode.HTML
        )

    if not url_match:
        await message.answer(
            "❌ Укажите ссылку на товар OZON\n\n"
            "Пример:\n<code>/add https://www.ozon.ru/product/...</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    url = url_match.group(0)
    
    # Проверяем лимит
    count = await db.count_user_products(message.from_user.id)
    if count >= MAX_PRODUCTS_PER_USER:
        await message.answer(
            f"❌ Достигнут лимит товаров ({MAX_PRODUCTS_PER_USER})\n"
            "Удалите ненужные: /delete",
            parse_mode=ParseMode.HTML
        )
        return
    
    status_msg = await message.answer("⏳ Получаю данные о товаре...")
    
    try:
        # Парсим товар в отдельном потоке
        product_data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: parser.parse_product(url)
        )
        
        if not product_data or product_data['price'] is None:
            await status_msg.edit_text(
                "❌ Не удалось получить данные\n\n"
                "Возможные причины:\n"
                "• Неверная ссылка\n"
                "• Проблемы с прокси\n"
                "• Товар недоступен\n\n"
                "Попробуйте позже или проверьте ссылку",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Добавляем в БД
        product_id = await db.add_product(message.from_user.id, url)
        
        await db.update_product_price(
            product_id,
            product_data['price'],
            product_data['in_stock'],
            product_data['stock_quantity'],
            product_data['name']
        )
        
        stock_emoji = "✅" if product_data['in_stock'] else "❌"
        response = f"""
✅ <b>Товар добавлен!</b>

🆔 ID: {product_id}
📦 {product_data['name']}

💰 Цена: {product_data['price']:.0f} ₽
{stock_emoji} {product_data['stock_quantity']}

Буду проверять цену каждые 10 минут!
"""
        await status_msg.edit_text(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении товара: {e}")
        await status_msg.edit_text("❌ Ошибка при добавлении товара")


@dp.message(Command("proxy_add"))
async def cmd_proxy_add(message: Message):
    """Добавление прокси"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажите прокси\n\n"
            "<b>Форматы:</b>\n"
            "• <code>IP:PORT:LOGIN:PASSWORD</code>\n"
            "• <code>IP:PORT</code>\n"
            "• <code>http://IP:PORT</code>\n\n"
            "Пример:\n<code>/proxy_add 1.2.3.4:8080:user:pass</code>",
            parse_mode=ParseMode.HTML
        )
        return

    raw = _clean_text(args[1])
    candidates = re.split(r"[\s,;]+", raw.strip())
    added = []

    proxies = _load_proxies()
    existing = set(proxies)

    for c in candidates:
        if not c:
            continue
        normalized = _normalize_proxy(c)
        if normalized and normalized not in existing:
            proxies.append(normalized)
            existing.add(normalized)
            added.append(normalized)

    _save_proxies(proxies)

    if added:
        await message.answer(f"✅ Добавлено прокси: {len(added)}")
    else:
        await message.answer("❌ Прокси не добавлены (неверный формат или дубликаты)")


@dp.message(Command("proxy_list"))
async def cmd_proxy_list(message: Message):
    """Список прокси"""
    proxies = _load_proxies()
    if not proxies:
        await message.answer("📭 Список прокси пуст. Добавьте: /proxy_add")
        return

    def mask(p: str) -> str:
        # Маскируем пароль
            parts = p.split(":")
        if len(parts) >= 4:
            return f"{parts[0]}:{parts[1]}:{parts[2]}:***"
        return p

    lines = [f"{i+1}. {mask(p)}" for i, p in enumerate(proxies[:20])]
    suffix = f"\n... и ещё {len(proxies) - 20}" if len(proxies) > 20 else ""
    
    await message.answer(
        f"📋 <b>Прокси ({len(proxies)}):</b>\n" + "\n".join(lines) + suffix,
        parse_mode=ParseMode.HTML
    )


@dp.message(Command("proxy_del"))
async def cmd_proxy_del(message: Message):
    """Удаление прокси"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите номер: <code>/proxy_del 1</code>", parse_mode=ParseMode.HTML)
        return

    try:
        idx = int(args[1]) - 1
    except ValueError:
        await message.answer("❌ Неверный номер")
        return

    proxies = _load_proxies()
    if idx < 0 or idx >= len(proxies):
        await message.answer("❌ Неверный номер прокси")
        return

    removed = proxies.pop(idx)
    _save_proxies(proxies)
    await message.answer(f"✅ Удалено: {removed[:40]}...")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Команда /list"""
    products = await db.get_user_products(message.from_user.id)
    
    if not products:
        await message.answer(
            "📭 Нет отслеживаемых товаров\n\nДобавьте: /add <ссылка>",
            parse_mode=ParseMode.HTML
        )
        return
    
    response = "📋 <b>Ваши товары:</b>\n\n"
    
    for p in products:
        stock_emoji = "✅" if p['in_stock'] else "❌"
        price_text = f"{p['current_price']:.0f} ₽" if p['current_price'] else "—"
        last_check = p['last_check'][:16] if p['last_check'] else "Не проверялось"
        
        response += f"""🆔 <b>ID {p['id']}</b>
📦 {p['product_name'] or 'Загружается...'}
💰 {price_text} {stock_emoji}
🕐 {last_check}
<a href="{p['url']}">Ссылка</a>

"""
    
    response += "💡 /history ID или /chart ID для истории цен"
    await message.answer(response, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    """Команда /delete"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Укажите ID: <code>/delete 1</code>", parse_mode=ParseMode.HTML)
            return
        
        product_id = int(args[1])
        success = await db.delete_product(product_id, message.from_user.id)
        
        if success:
            await message.answer(f"✅ Товар #{product_id} удален")
        else:
            await message.answer("❌ Товар не найден")
            
    except ValueError:
        await message.answer("❌ Неверный ID")


@dp.message(Command("history"))
async def cmd_history(message: Message):
    """Команда /history"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Укажите ID: <code>/history 1</code>", parse_mode=ParseMode.HTML)
            return
        
        product_id = int(args[1])
        
        product = await db.get_product(product_id)
        if not product or product['user_id'] != message.from_user.id:
            await message.answer("❌ Товар не найден")
            return
        
        history = await db.get_price_history(product_id, limit=30)
        
        if not history:
            await message.answer("📭 История пуста")
            return
        
        response = f"📊 <b>История цен</b>\n📦 {product['product_name']}\n\n"
        
        for record in history[-20:]:
            date = record['checked_at'][:16]
            price = record['price']
            stock = "✅" if record['in_stock'] else "❌"
            response += f"{date} — {price:.0f} ₽ {stock}\n"
        
        if len(history) > 20:
            response += f"\n... и еще {len(history) - 20} записей"
        
        response += "\n\n💡 /chart для графика"
        await message.answer(response, parse_mode=ParseMode.HTML)
        
    except ValueError:
        await message.answer("❌ Неверный ID")


@dp.message(Command("chart"))
async def cmd_chart(message: Message):
    """Команда /chart"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Укажите ID: <code>/chart 1</code>", parse_mode=ParseMode.HTML)
            return
        
        product_id = int(args[1])
        
        product = await db.get_product(product_id)
        if not product or product['user_id'] != message.from_user.id:
            await message.answer("❌ Товар не найден")
            return
        
        history = await db.get_price_history(product_id)
        
        if len(history) < 2:
            await message.answer("❌ Недостаточно данных (нужно минимум 2 проверки)")
            return
        
        status_msg = await message.answer("📊 Создаю график...")
        
        chart_buffer = chart_gen.generate_price_chart(history, product['product_name'])
        
        if chart_buffer:
            photo = BufferedInputFile(chart_buffer.read(), filename="chart.png")
            await message.answer_photo(photo, caption=f"📊 {product['product_name'][:100]}")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Ошибка создания графика")
        
    except ValueError:
        await message.answer("❌ Неверный ID")


@dp.message(F.text.regexp(r'https?://(?:www\.)?ozon\.ru/\S+'))
async def handle_url(message: Message):
    """Обработка прямых ссылок"""
    message.text = f"/add {message.text}"
    await cmd_add(message)


async def main():
    """Запуск бота"""
        await db.init_db()
    logger.info("✅ База данных инициализирована")
    logger.info("🚀 Бот запущен!")
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
