# services/api-gateway/Dockerfile
FROM python:3.12-slim

# system deps (e.g. for psycopg2)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy shared libs
COPY ../../libs/common-utils /app/libs/common-utils
COPY ../../libs/common-schemas /app/libs/common-schemas

# copy this service
COPY . /app

# install shared libs + this service
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app/libs/common-schemas \
      -e /app

# port and entrypoint
EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
