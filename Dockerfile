FROM python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN reflex init

CMD ["sh", "-c", "reflex run --env prod --frontend-port ${PORT:-10000}"]