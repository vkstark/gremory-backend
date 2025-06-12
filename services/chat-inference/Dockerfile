# services/chat-inference/Dockerfile
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy shared libs
COPY ../libs/common-utils /app/libs/common-utils
COPY ../services/user-history /app/services/user-history

# copy this service
COPY ./services/chat-inference /app

# install dependencies
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app/services/user-history \
      -e /app \
      -r requirements.txt

# expose if you plan to hit it directly; usually gateway proxies to it
EXPOSE 8000
CMD ["uvicorn", "src.chat_inference.main:app", "--host", "0.0.0.0", "--port", "8002"]
