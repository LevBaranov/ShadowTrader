# Образ Telegram-бота.
#
# Контекст сборки — каталог bot/, а не корень репозитория: в образ физически
# не может попасть код бэкенда. Бот общается с ним только по REST API
# (API_BASE_URL) и имеет собственные зависимости (bot/requirements.txt).
#
#   docker build -f bot.Dockerfile -t shadowtrader-bot ./bot
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./bot/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
