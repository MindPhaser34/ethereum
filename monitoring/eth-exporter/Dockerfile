FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    prometheus_client \
    requests

COPY exporter.py .

RUN chmod +x exporter.py

EXPOSE 9333

CMD ["python", "-u", "exporter.py"]
