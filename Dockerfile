FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# База SQLite хранится в /data: монтируйте туда volume, чтобы она переживала перезапуски.
ENV DB_URL=sqlite+aiosqlite:////data/bot.db
VOLUME /data

CMD ["python", "main.py"]
