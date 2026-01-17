"""
Парсер OZON на Playwright - обход антибот защиты

Техники из статьи: https://habr.com/ru/companies/amvera/articles/960280/
"""

import re
import asyncio
import random
import logging
import os
from typing import Dict, Optional, List

from bs4 import BeautifulSoup

# Настройки
HEADLESS_MODE = True
PARSER_TIMEOUT = 30000  # миллисекунды
PAGE_LOAD_DELAY = 5
PRICE_MIN = 100
PRICE_MAX = 5_000_000

logger = logging.getLogger(__name__)


class OzonParser:
    """Парсер OZON с обходом антибот защиты через Playwright"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._proxy_list: List[str] = []
        self._proxy_index = 0
    
    def load_proxies(self, proxy_file: str = None):
        """Загрузка прокси из файла"""
        if proxy_file and os.path.exists(proxy_file):
            try:
                self._proxy_list = []
                with open(proxy_file, 'r') as f:
                    for line in f:
                        proxy = line.strip()
                        if proxy:
                            self._proxy_list.append(proxy)
                logger.info(f"✅ Загружено {len(self._proxy_list)} прокси")
            except Exception as e:
                logger.error(f"Ошибка загрузки прокси: {e}")
    
    def _get_next_proxy(self) -> Optional[str]:
        """Получить следующий прокси (ротация)"""
        if not self._proxy_list:
            return None
        proxy = self._proxy_list[self._proxy_index % len(self._proxy_list)]
        self._proxy_index += 1
        return proxy

    async def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Имитация человеческой задержки между действиями"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def _setup_browser(self, proxy: Optional[str] = None):
        """Инициализация браузера Playwright с настройками маскировки"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        
        # Настройка прокси
        proxy_config = None
            if proxy:
            # Формат: IP:PORT:LOGIN:PASSWORD или socks5://...
            if proxy.startswith("socks5://") or proxy.startswith("http://"):
                proxy_config = {"server": proxy}
                        else:
                parts = proxy.split(":")
                if len(parts) >= 4:
                    ip, port, login, password = parts[0], parts[1], parts[2], ":".join(parts[3:])
                    proxy_config = {
                        "server": f"http://{ip}:{port}",
                        "username": login,
                        "password": password
                    }
                elif len(parts) == 2:
                    proxy_config = {"server": f"http://{proxy}"}
            
            if proxy_config:
                logger.info(f"🌐 Используется прокси: {proxy[:40]}...")
        
        # Запуск браузера с параметрами для обхода детекции
        self.browser = await self.playwright.chromium.launch(
            headless=HEADLESS_MODE,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # Создание контекста с маскировкой
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            proxy=proxy_config,
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
        )
        
        # Скрипты для маскировки автоматизации
        await self.context.add_init_script("""
            // Удаляем navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Добавляем window.chrome
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Настраиваем plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Настраиваем languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
            
            // Маскируем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(PARSER_TIMEOUT)
        self.page.set_default_navigation_timeout(PARSER_TIMEOUT)
        
        logger.info("✅ Браузер Playwright запущен")
    
    async def _simulate_human_behavior(self):
        """Имитация человеческого поведения на странице"""
        if not self.page:
            return
        
        try:
            # Случайные движения мыши
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await self.page.mouse.move(x, y, steps=random.randint(5, 15))
                await self._human_delay(0.1, 0.3)
            
            # Плавный скролл
            scroll_steps = random.randint(2, 5)
            for _ in range(scroll_steps):
                scroll_amount = random.randint(100, 300)
                await self.page.evaluate(f"""
                    window.scrollBy({{
                        top: {scroll_amount},
                        left: 0,
                        behavior: 'smooth'
                    }});
                """)
                await self._human_delay(0.3, 0.7)
            
            # Возврат наверх
            await self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
            await self._human_delay(0.3, 0.5)
            
            except Exception as e:
            logger.debug(f"Ошибка при имитации поведения: {e}")
    
    async def _warm_up(self):
        """Warm-up: загрузка главной страницы для создания сессии"""
        if not self.page:
            return False
        
        try:
            logger.info("🔥 Warm-up: загружаю главную страницу OZON...")
            await self.page.goto("https://www.ozon.ru", wait_until='domcontentloaded', timeout=30000)
            await self._human_delay(2, 4)
            await self._simulate_human_behavior()
            await self._human_delay(1, 2)
            logger.info("✅ Warm-up завершен")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Warm-up не удался: {e}")
            return False

    async def _close_browser(self):
        """Закрытие браузера"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception:
            pass
    
    def _detect_antibot(self, html: str) -> bool:
        """Обнаружение антибот защиты"""
        html_lower = html.lower()
        
        antibot_keywords = [
            'antibot', 'доступ ограничен', 'access denied', 'captcha',
            'подтвердите, что вы не робот', 'я не робот', 'recaptcha',
            'hcaptcha', 'cloudflare', 'checking your browser', 'just a moment',
            'fastly', 'bot management', 'challenge', 'fab_chlg_',
        ]
        
        for keyword in antibot_keywords:
            if keyword in html_lower:
                logger.debug(f"🔍 Обнаружен антибот: {keyword}")
                return True
        
        # Проверка по размеру HTML без контента OZON
        if 150000 < len(html) < 250000:
            ozon_indicators = [
                'data-widget="webProductHeading"',
                'data-widget="webPrice"',
                'ozon.ru/product/',
            ]
            if not any(indicator in html for indicator in ozon_indicators):
                return True
        
        return False
    
    async def _bypass_antibot(self, max_attempts: int = 3) -> bool:
        """Попытка обхода антибот защиты"""
        if not self.page:
        return False
    
        logger.info("🔄 Пытаюсь обойти антибот защиту...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Попытка {attempt}/{max_attempts}...")
                
                # 1. Ищем и нажимаем кнопку "Обновить"
                try:
                    reload_button = await self.page.query_selector("#reload-button")
                    if reload_button:
                        await reload_button.click()
                        logger.info("✅ Нажата кнопка 'Обновить'")
                        await self._human_delay(8, 12)
                        
                        html = await self.page.content()
                        if not self._detect_antibot(html):
                            return True
                    except Exception:
                        pass
                
                # 2. Имитация человеческого поведения
                await self._simulate_human_behavior()
                await self._human_delay(2, 4)
                
                html = await self.page.content()
                if not self._detect_antibot(html):
                    return True
                
                # 3. Ожидание автоматического прохождения
                for _ in range(5):
                    await self._human_delay(2, 4)
                    html = await self.page.content()
                    if not self._detect_antibot(html):
                        logger.info("✅ Антибот пройден автоматически!")
                        return True
                
                # 4. Перезагрузка страницы
                if attempt < max_attempts:
                    logger.info("🔄 Перезагружаю страницу...")
                    await self.page.reload(wait_until='domcontentloaded', timeout=30000)
                    await self._human_delay(3, 6)
                    
                    html = await self.page.content()
                    if not self._detect_antibot(html):
                        return True
                    
                            except Exception as e:
                logger.error(f"Ошибка в попытке {attempt}: {e}")
        
        logger.warning("⚠️ Не удалось обойти антибот защиту")
        return False
    
    async def _wait_for_content(self):
        """Ожидание появления контента товара"""
        if not self.page:
            return
        
        selectors = [
            "[data-widget='webPrice']",
            "[data-widget='webProductHeading']",
            "h1",
        ]
        
        for selector in selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=8000)
                return
            except Exception:
                    continue
    
    def _parse_name(self, soup) -> str:
        """Парсинг названия товара"""
        try:
            heading = soup.find('h1', {'data-widget': 'webProductHeading'})
            if heading:
                return heading.get_text(strip=True)[:100]
            
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)[:100]
            
            return "Неизвестный товар"
        except Exception:
            return "Неизвестный товар"
    
    def _parse_price(self, html: str, soup) -> Optional[float]:
        """Парсинг цены"""
        try:
            # 1. Поиск по data-widget="webPrice"
            price_widget = soup.find(attrs={'data-widget': 'webPrice'})
            if price_widget:
                price_text = price_widget.get_text()
                # Ищем цену (число с пробелами + ₽)
                match = re.search(r'([\d\s]+)\s*₽', price_text)
                if match:
                    price = float(match.group(1).replace(' ', '').replace('\xa0', ''))
                    if PRICE_MIN <= price <= PRICE_MAX:
                        return price
            
            # 2. Поиск по паттернам в HTML
        patterns = [
                r'(\d[\d\s]{2,})\s*₽',
                r'₽\s*(\d[\d\s]{2,})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    price = float(match.group(1).replace(' ', '').replace('\xa0', ''))
                    if PRICE_MIN <= price <= PRICE_MAX:
                        return price

        return None
            except Exception:
            return None

    def _parse_stock(self, html: str) -> tuple:
        """Парсинг наличия"""
        text = html.lower()
        if any(p in text for p in ['нет в наличии', 'закончился', 'товар закончился']):
            return False, "Нет в наличии"
        return True, "В наличии"

    async def parse_product_async(self, url: str) -> Optional[Dict]:
        """Асинхронный парсинг товара"""
        max_attempts = 2
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 Попытка {attempt}/{max_attempts} парсинга: {url[:50]}...")
                
                # Получаем прокси
                proxy = self._get_next_proxy()
                
                # Инициализация браузера
                await self._setup_browser(proxy)
                
                # Warm-up при первой попытке
                if attempt == 1:
                    await self._warm_up()
                
                # Загрузка страницы товара
                logger.info("📥 Загружаю страницу товара...")
                try:
                    await self.page.goto(url, wait_until='domcontentloaded', timeout=PARSER_TIMEOUT)
                    except Exception as e:
                    logger.warning(f"⚠️ Таймаут загрузки: {e}")
                
                await self._wait_for_content()
                await self._human_delay(PAGE_LOAD_DELAY, PAGE_LOAD_DELAY + 2)
                
                html = await self.page.content()
                logger.info(f"📄 Страница загружена ({len(html):,} байт)")
                
                # Проверка на антибот
                if self._detect_antibot(html):
                    logger.warning("🚫 Обнаружена антибот защита")
                    if await self._bypass_antibot():
                        html = await self.page.content()
                    else:
                        await self._close_browser()
                    continue
            
                # Парсинг данных
            soup = BeautifulSoup(html, 'html.parser')
            name = self._parse_name(soup)
            price = self._parse_price(html, soup)
            
            if price:
                    in_stock, stock_text = self._parse_stock(html)
                result = {
                    'name': name,
                    'price': price,
                        'in_stock': in_stock,
                    'stock_quantity': stock_text,
                }
                    logger.info(f"✅ НАЙДЕНО: {name[:40]}... = {price:.0f} ₽")
                    await self._close_browser()
                return result
            else:
                    logger.warning("❌ Цена не найдена")
                    await self._close_browser()
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в попытке {attempt}: {e}")
                await self._close_browser()
        
        logger.error("❌ Все попытки парсинга неудачны")
                return None
                
    def parse_product(self, url: str, **kwargs) -> Optional[Dict]:
        """Синхронная обертка для парсинга (для совместимости)"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.parse_product_async(url))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return None


# Тест
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    parser = OzonParser()
    url = "https://www.ozon.ru/product/nabor-igrovoy-dlya-devochki-kuhnya-s-produktami-i-posudu-1628022641"
    
    result = parser.parse_product(url)
    print("Результат:", result)
