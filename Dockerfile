# Analog clock worksheet — FastAPI + Uvicorn
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/output \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "analog_clock_worksheet.web:app", "--host", "0.0.0.0", "--port", "8000"]
