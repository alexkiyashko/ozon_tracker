"""
Модуль для работы с базой данных SQLite
"""

import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных приложения"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица товаров
            await db.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    url TEXT NOT NULL,
                    product_name TEXT,
                    current_price REAL,
                    last_check TIMESTAMP,
                    in_stock BOOLEAN DEFAULT 1,
                    stock_quantity TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица истории цен
            await db.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    price REAL,
                    in_stock BOOLEAN,
                    stock_quantity TEXT,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')
            
            # Создание индексов для ускорения запросов
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_user 
                ON products(user_id, is_active)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_price_history_product 
                ON price_history(product_id, checked_at)
            ''')
            
            await db.commit()
            logger.info("База данных инициализирована")
    
    async def add_user(self, user_id: int, username: str = None):
        """Добавление пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
                (user_id, username)
            )
            await db.commit()
    
    async def add_product(self, user_id: int, url: str) -> int:
        """Добавление товара для отслеживания"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'INSERT INTO products (user_id, url) VALUES (?, ?)',
                (user_id, url)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_user_products(self, user_id: int) -> List[Dict]:
        """Получение списка товаров пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT * FROM products 
                   WHERE user_id = ? AND is_active = 1 
                   ORDER BY added_at DESC''',
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_all_active_products(self) -> List[Dict]:
        """Получение всех активных товаров для мониторинга"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM products WHERE is_active = 1'
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def update_product_price(self, product_id: int, price: float, 
                                   in_stock: bool, stock_quantity: str = None,
                                   product_name: str = None):
        """Обновление информации о товаре и добавление записи в историю"""
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем текущую информацию о товаре
            update_query = '''
                UPDATE products 
                SET current_price = ?, last_check = ?, in_stock = ?, stock_quantity = ?
            '''
            params = [price, datetime.now(), in_stock, stock_quantity]
            
            if product_name:
                update_query += ', product_name = ?'
                params.append(product_name)
            
            update_query += ' WHERE id = ?'
            params.append(product_id)
            
            await db.execute(update_query, params)
            
            # Добавляем запись в историю цен
            await db.execute(
                '''INSERT INTO price_history (product_id, price, in_stock, stock_quantity) 
                   VALUES (?, ?, ?, ?)''',
                (product_id, price, in_stock, stock_quantity)
            )
            await db.commit()
            logger.debug(f"Обновлена цена товара #{product_id}: {price} ₽")
    
    async def get_price_history(self, product_id: int, limit: int = None) -> List[Dict]:
        """Получение истории цен товара"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = '''SELECT * FROM price_history 
                       WHERE product_id = ? 
                       ORDER BY checked_at ASC'''
            
            if limit:
                query += f' LIMIT {limit}'
            
            async with db.execute(query, (product_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def delete_product(self, product_id: int, user_id: int) -> bool:
        """Удаление товара (мягкое удаление - деактивация)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'UPDATE products SET is_active = 0 WHERE id = ? AND user_id = ?',
                (product_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def get_product(self, product_id: int) -> Optional[Dict]:
        """Получение информации о товаре по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM products WHERE id = ?',
                (product_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def count_user_products(self, user_id: int) -> int:
        """Подсчет количества активных товаров пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT COUNT(*) FROM products WHERE user_id = ? AND is_active = 1',
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0]
    
    async def get_statistics(self) -> Dict:
        """Получение общей статистики"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Количество пользователей
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                stats['total_users'] = (await cursor.fetchone())[0]
            
            # Количество активных товаров
            async with db.execute(
                'SELECT COUNT(*) FROM products WHERE is_active = 1'
            ) as cursor:
                stats['active_products'] = (await cursor.fetchone())[0]
            
            # Количество записей в истории
            async with db.execute('SELECT COUNT(*) FROM price_history') as cursor:
                stats['history_records'] = (await cursor.fetchone())[0]
            
            return stats
