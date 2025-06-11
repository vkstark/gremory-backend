# services/chat-inference/Dockerfile
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy shared libs
COPY ../../libs/common-utils /app/libs/common-utils
COPY ../../libs/common-schemas /app/libs/common-schemas

# copy this service
COPY . /app

# install dependencies
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app/libs/common-schemas \
      -e /app

# expose if you plan to hit it directly; usually gateway proxies to it
EXPOSE 8000
CMD ["uvicorn", "chat_inference.chat:app", "--host", "0.0.0.0", "--port", "8000"]
