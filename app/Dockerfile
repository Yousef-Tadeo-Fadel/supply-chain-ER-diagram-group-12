FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY . .
USER appuser
EXPOSE 8000
CMD ["gunicorn", "--preload", "--workers", "2", "--threads", "2", "--bind", "0.0.0.0:8000", "app:app"]

