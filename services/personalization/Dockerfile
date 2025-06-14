# services/personalization/Dockerfile
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# shared libs
COPY ../libs/common-utils /app/libs/common-utils

# service
COPY ./services/personalization /app

# install
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app \
      -r requirements.txt

# EXPOSE 8000
CMD ["uvicorn", "src.personalization.main:app", "--host", "0.0.0.0", "--port", "8004"]
