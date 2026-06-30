FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY bot/ bot/
COPY scout/ scout/

CMD ["python3.12", "-m", "bot.main"]
