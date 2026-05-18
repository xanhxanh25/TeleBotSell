FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/APITELE

COPY requirements.txt /tmp/apitele-requirements.txt
RUN pip install --no-cache-dir -r /tmp/apitele-requirements.txt

COPY . /app/APITELE

CMD ["python", "run.py"]
