FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=10000 \
    SPECTOOM_ENV=production \
    SPECTOOM_DATA_DIR=/var/data/spectoom \
    SPECTOOM_SECURE_COOKIES=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /var/data/spectoom

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import json,os,urllib.request; p=os.environ.get('PORT','10000'); d=json.load(urllib.request.urlopen('http://127.0.0.1:'+p+'/api/health',timeout=4)); assert d.get('ok')"

CMD ["python", "server.py"]
