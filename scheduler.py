"""
Планировщик автоматической проверки цен
"""

import asyncio
import logging
from aiogram import Bot

from config import BOT_TOKEN, CHECK_INTERVAL, PARSER_DELAY, LOG_LEVEL, LOG_FORMAT, PROXY_STORAGE_PATH
from database import Database
from parser import OzonParser

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class PriceChecker:
    """Автоматическая проверка цен"""
    
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.db = Database("ozon_tracker.db")
        self.parser = OzonParser()
        self.parser.load_proxies(PROXY_STORAGE_PATH)
    
    async def check_prices(self):
        """Проверка всех товаров"""
        logger.info("=== Начало проверки цен ===")
        
        try:
            products = await self.db.get_all_active_products()
            logger.info(f"Активных товаров: {len(products)}")
            
            for i, product in enumerate(products, 1):
                try:
                    logger.info(f"[{i}/{len(products)}] Товар #{product['id']}")
                    await self.check_single_product(product)
                    
                    if i < len(products):
                        await asyncio.sleep(PARSER_DELAY)
                        
                except Exception as e:
                    logger.error(f"Ошибка товара #{product['id']}: {e}")
            
            logger.info("=== Проверка завершена ===")
            
        except Exception as e:
            logger.error(f"Ошибка в цикле проверки: {e}")
    
    async def check_single_product(self, product: dict):
        """Проверка одного товара"""
        try:
            # Парсим в отдельном потоке
            product_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.parser.parse_product(product['url'])
            )
            
            if not product_data or product_data['price'] is None:
                logger.warning(f"Нет данных для товара #{product['id']}")
                return
            
            new_price = product_data['price']
            old_price = product['current_price']
            new_stock = product_data['in_stock']
            old_stock = product['in_stock']
            
            # Обновляем БД
            await self.db.update_product_price(
                product['id'],
                new_price,
                new_stock,
                product_data['stock_quantity'],
                product_data['name']
            )
            
            # Уведомления
            await self.send_notifications(product, old_price, new_price, old_stock, new_stock)
            
            logger.info(f"✅ #{product['id']}: {new_price}₽")
            
        except Exception as e:
            logger.error(f"❌ Товар #{product['id']}: {e}")
    
    async def send_notifications(self, product: dict, old_price: float, 
                                 new_price: float, old_stock: bool, new_stock: bool):
        """Отправка уведомлений"""
        user_id = product['user_id']
        
        # Снижение цены
        if old_price and new_price < old_price:
            discount = old_price - new_price
            discount_percent = (discount / old_price) * 100
            
            message = f"""
🔔 <b>Цена снизилась!</b>

📦 {product['product_name']}

💰 Было: {old_price:.0f} ₽
💵 Стало: {new_price:.0f} ₽
📉 Скидка: {discount:.0f} ₽ (-{discount_percent:.1f}%)

<a href="{product['url']}">Перейти к товару</a>
"""
            try:
                await self.bot.send_message(user_id, message, parse_mode="HTML", disable_web_page_preview=True)
                logger.info(f"✅ Уведомление о снижении → {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
        
        # Повышение цены (>5%)
        elif old_price and new_price > old_price:
            increase_percent = ((new_price - old_price) / old_price) * 100
            
            if increase_percent > 5:
                message = f"""
📈 <b>Цена выросла</b>

📦 {product['product_name']}

💰 Было: {old_price:.0f} ₽
💵 Стало: {new_price:.0f} ₽
📈 Рост: +{increase_percent:.1f}%

<a href="{product['url']}">Перейти к товару</a>
"""
                try:
                    await self.bot.send_message(user_id, message, parse_mode="HTML", disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Ошибка отправки: {e}")
        
        # Появление в наличии
        if not old_stock and new_stock:
            message = f"""
✅ <b>Товар появился!</b>

📦 {product['product_name']}
💰 Цена: {new_price:.0f} ₽

<a href="{product['url']}">Перейти к товару</a>
"""
            try:
                await self.bot.send_message(user_id, message, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
        
        # Закончился товар
        if old_stock and not new_stock:
            message = f"""
❌ <b>Товар закончился</b>

📦 {product['product_name']}

<a href="{product['url']}">Ссылка</a>
"""
            try:
                await self.bot.send_message(user_id, message, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
    
    async def run(self):
        """Основной цикл"""
        await self.db.init_db()
        logger.info(f"📅 Планировщик запущен. Интервал: {CHECK_INTERVAL//60} мин")
        
        while True:
            try:
                await self.check_prices()
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
            
            logger.info(f"⏰ Следующая проверка через {CHECK_INTERVAL//60} мин")
            await asyncio.sleep(CHECK_INTERVAL)


async def main():
    checker = PriceChecker()
    await checker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен")
