# Zenith'i Render / Fly.io / Railway gibi ucretsiz katmani olan herhangi bir
# container hostunda calistirmak icin:
#   docker build -t zenith . && docker run -p 8000:8000 zenith
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY zenith/ zenith/
COPY config/ config/
COPY static/ static/

EXPOSE 8000

# Render/Railway PORT ortam degiskeni verir; yoksa 8000 kullanilir.
CMD ["sh", "-c", "uvicorn zenith.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
