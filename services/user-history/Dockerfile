# services/user-history/Dockerfile
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# shared libs
COPY ../../libs/common-utils /app/libs/common-utils
COPY ../../libs/common-schemas /app/libs/common-schemas

# service code
COPY . /app

# install
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app/libs/common-schemas \
      -e /app

EXPOSE 8000
CMD ["uvicorn", "user_history.history:app", "--host", "0.0.0.0", "--port", "8000"]
