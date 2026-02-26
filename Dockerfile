FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered stdout (better for Docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py storage.py monitor.py bot.py main.py ./

# SQLite database lives here; mount a host volume to persist across restarts
VOLUME ["/app/data"]

CMD ["python", "main.py"]
