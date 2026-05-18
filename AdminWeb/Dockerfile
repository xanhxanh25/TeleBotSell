FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY AdminWeb/requirements.txt /tmp/adminweb-requirements.txt
RUN pip install --no-cache-dir -r /tmp/adminweb-requirements.txt

COPY AdminWeb /app/AdminWeb
COPY token_shop_backend /app/token_shop_backend

WORKDIR /app/AdminWeb

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
