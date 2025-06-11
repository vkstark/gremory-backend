# services/api-gateway/Dockerfile
FROM python:3.12-slim

# system deps (e.g. for psycopg2)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy shared libs
COPY ../libs/common-utils /app/libs/common-utils

# copy this service
COPY ./services/api-gateway /app

# install shared libs + this service
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app \
      -r requirements.txt

# port and entrypoint
EXPOSE 8000
CMD ["uvicorn", "src.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
