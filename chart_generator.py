"""
Модуль для генерации графиков изменения цен
"""

import os
import config as cfg

RUNTIME_DIR = getattr(cfg, "RUNTIME_DIR", "/tmp/ozon_runtime")
MPLCONFIGDIR = getattr(cfg, "MPLCONFIGDIR", f"{RUNTIME_DIR}/mpl")
os.makedirs(MPLCONFIGDIR, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", MPLCONFIGDIR)

import matplotlib
matplotlib.use('Agg')  # Backend без GUI для серверов
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import List, Dict, Optional
import io
import logging

from config import CHART_SIZE, CHART_DPI, MAX_CHART_RECORDS

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Генератор графиков изменения цен"""
    
    @staticmethod
    def generate_price_chart(price_history: List[Dict], product_name: str) -> Optional[io.BytesIO]:
        """
        Генерация графика изменения цен
        
        Args:
            price_history: Список записей истории цен
            product_name: Название товара
            
        Returns:
            BytesIO: Буфер с изображением графика
            None: Если данных недостаточно
        """
        try:
            if not price_history or len(price_history) < 2:
                logger.warning("Недостаточно данных для построения графика")
                return None
            
            # Ограничиваем количество записей
            if len(price_history) > MAX_CHART_RECORDS:
                price_history = price_history[-MAX_CHART_RECORDS:]
            
            # Подготовка данных
            dates = []
            prices = []
            
            for record in price_history:
                if record['price'] is not None:
                    try:
                        # Парсим дату
                        date_str = record['checked_at']
                        if '.' in date_str:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
                        else:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        
                        dates.append(date_obj)
                        prices.append(record['price'])
                    except Exception as e:
                        logger.error(f"Ошибка парсинга даты: {e}")
                        continue
            
            if len(prices) < 2:
                logger.warning("Недостаточно валидных данных для графика")
                return None
            
            # Создание графика
            plt.figure(figsize=CHART_SIZE)
            plt.plot(dates, prices, marker='o', linestyle='-', linewidth=2, 
                    markersize=6, color='#2E86DE', markerfacecolor='#54A0FF')
            
            # Настройка заголовка
            title = f'История изменения цены\n{product_name[:60]}'
            if len(product_name) > 60:
                title += '...'
            plt.title(title, fontsize=14, fontweight='bold', pad=20)
            
            # Подписи осей
            plt.xlabel('Дата и время', fontsize=12)
            plt.ylabel('Цена (₽)', fontsize=12)
            
            # Сетка
            plt.grid(True, alpha=0.3, linestyle='--')
            
            # Форматирование оси X (даты)
            plt.gcf().autofmt_xdate()
            if len(dates) > 20:
                date_format = mdates.DateFormatter('%d.%m')
            else:
                date_format = mdates.DateFormatter('%d.%m %H:%M')
            plt.gca().xaxis.set_major_formatter(date_format)
            
            # Добавление значений на точки (не для всех, если их много)
            step = max(1, len(dates) // 10)  # Показываем максимум 10 значений
            for i in range(0, len(dates), step):
                plt.annotate(f'{prices[i]:.0f}₽', 
                           (dates[i], prices[i]),
                           textcoords="offset points",
                           xytext=(0, 10),
                           ha='center',
                           fontsize=9,
                           bbox=dict(boxstyle='round,pad=0.3', 
                                   facecolor='yellow', 
                                   alpha=0.7))
            
            # Расчет статистики
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            current_price = prices[-1]
            
            # Изменение цены
            if len(prices) > 1:
                price_change = current_price - prices[0]
                price_change_percent = (price_change / prices[0]) * 100
                change_symbol = '📉' if price_change < 0 else ('📈' if price_change > 0 else '➡️')
            else:
                price_change = 0
                price_change_percent = 0
                change_symbol = '➡️'
            
            # Статистика внизу
            stats_text = (
                f'Текущая: {current_price:.0f}₽ {change_symbol} '
                f'| Мин: {min_price:.0f}₽ | Макс: {max_price:.0f}₽ '
                f'| Средняя: {avg_price:.0f}₽ | Изменение: {price_change:+.0f}₽ ({price_change_percent:+.1f}%)'
            )
            
            plt.figtext(0.5, 0.02, stats_text, ha='center', fontsize=10,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
            
            # Отступы
            plt.tight_layout()
            plt.subplots_adjust(bottom=0.15)
            
            # Сохранение в буфер
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=CHART_DPI, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            
            logger.info(f"График успешно создан ({len(prices)} точек)")
            return buf
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика: {e}", exc_info=True)
            plt.close()
            return None


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Тестовые данные
    test_data = [
        {'checked_at': '2026-01-10 10:00:00', 'price': 15990},
        {'checked_at': '2026-01-10 12:00:00', 'price': 15890},
        {'checked_at': '2026-01-10 14:00:00', 'price': 15990},
        {'checked_at': '2026-01-11 10:00:00', 'price': 14990},
        {'checked_at': '2026-01-11 12:00:00', 'price': 14890},
    ]
    
    chart_gen = ChartGenerator()
    result = chart_gen.generate_price_chart(test_data, "Тестовый товар")
    
    if result:
        with open('/tmp/test_chart.png', 'wb') as f:
            f.write(result.read())
        print("✅ График сохранен в /tmp/test_chart.png")
    else:
        print("❌ Ошибка создания графика")
