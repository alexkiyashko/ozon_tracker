#!/bin/bash

# ============================================
# OZON Price Tracker - Установка
# Использует Playwright для обхода антибота
# ============================================

set -e

echo "🚀 OZON Price Tracker - Установка"
echo "=================================="
echo ""

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Требуются права root"
   echo "   Используйте: sudo bash install.sh"
   exit 1
fi

# Переменные
INSTALL_DIR="/opt/ozon_tracker"
RUNTIME_DIR="/root/ozon_runtime"

echo "📋 Директория: $INSTALL_DIR"
echo ""

# ШАГ 1: Обновление системы
echo "📦 Шаг 1/5: Обновление системы..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

# ШАГ 2: Установка зависимостей
echo "📦 Шаг 2/5: Установка зависимостей..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl

# Зависимости для Playwright
apt-get install -y -qq \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 2>/dev/null || true

echo "   ✅ Зависимости установлены"

# ШАГ 3: Создание директорий
echo "📁 Шаг 3/5: Создание директорий..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/.cache"
mkdir -p "$RUNTIME_DIR/.config"
mkdir -p "$RUNTIME_DIR/mpl"

cd "$INSTALL_DIR"

# Копируем файлы из текущей директории если есть
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
if [ -f "$SCRIPT_DIR/bot.py" ]; then
    echo "   Копирование файлов проекта..."
    cp -f "$SCRIPT_DIR"/*.py "$INSTALL_DIR/" 2>/dev/null || true
    cp -f "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true
fi

echo "   ✅ Директории созданы"

# ШАГ 4: Python окружение
echo "🐍 Шаг 4/5: Настройка Python..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

pip install --upgrade pip -q

if [ -f "requirements.txt" ]; then
    echo "   Установка зависимостей Python..."
    pip install -r requirements.txt --no-cache-dir -q
    echo "   ✅ Python зависимости установлены"
else
    echo "   ❌ requirements.txt не найден"
    deactivate
    exit 1
fi

# Установка браузеров Playwright
echo "🎭 Установка браузеров Playwright..."
export XDG_CACHE_HOME="$RUNTIME_DIR/.cache"
export XDG_CONFIG_HOME="$RUNTIME_DIR/.config"
export HOME="/root"

playwright install chromium --with-deps 2>&1 | head -20 || true
echo "   ✅ Playwright установлен"

deactivate

# ШАГ 5: Настройка systemd
echo "⚙️  Шаг 5/5: Настройка сервисов..."

cat > /etc/systemd/system/ozon-bot.service <<EOF
[Unit]
Description=OZON Price Tracker Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/bin"
Environment="HOME=/root"
Environment="XDG_CACHE_HOME=$RUNTIME_DIR/.cache"
Environment="XDG_CONFIG_HOME=$RUNTIME_DIR/.config"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/ozon-scheduler.service <<EOF
[Unit]
Description=OZON Price Checker
After=network.target ozon-bot.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/bin"
Environment="HOME=/root"
Environment="XDG_CACHE_HOME=$RUNTIME_DIR/.cache"
Environment="XDG_CONFIG_HOME=$RUNTIME_DIR/.config"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ozon-bot ozon-scheduler 2>/dev/null

chmod 600 "$INSTALL_DIR/config.py" 2>/dev/null || true

echo ""
echo "════════════════════════════════════════"
echo "✅ Установка завершена!"
echo "════════════════════════════════════════"
echo ""
echo "📝 Следующие шаги:"
echo ""
echo "1. Настройте токен бота:"
echo "   nano $INSTALL_DIR/config.py"
echo ""
echo "2. Запустите сервисы:"
echo "   systemctl start ozon-bot ozon-scheduler"
echo ""
echo "3. Проверьте логи:"
echo "   journalctl -u ozon-bot -f"
echo ""
echo "4. Откройте Telegram и отправьте боту /start"
echo ""
echo "💡 Полезные команды:"
echo "   systemctl status ozon-bot"
echo "   systemctl restart ozon-bot"
echo "   journalctl -u ozon-bot -n 50"
echo ""
