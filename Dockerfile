# Dockerfile (mono-repo, monolith)

# 1. Base image
FROM python:3.12-slim

# 2. Environment
ENV PYTHONUNBUFFERED=1

# 3. Install system deps for psycopg2, etc.
# RUN apt-get update \
#  && apt-get install -y --no-install-recommends \
#       build-essential \
#       libpq-dev \
#  && rm -rf /var/lib/apt/lists/*

# 4. Create app dir
WORKDIR /app

# Copy generic pip requirements (for base deps)
COPY requirements.txt /app/

# To copy in your .env file, uncomment the line below
# COPY .env /app/.env

# Install base deps
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy in your shared libraries
COPY libs/common-utils /app/libs/common-utils

# 6. Copy in all your services
COPY services /app/services

# 7. Install all packages in editable mode
#    This will register each service package (and shared libs) in site-packages
RUN pip install --no-cache-dir \
      -e /app/libs/common-utils \
      -e /app/services/api-gateway-monolith \
      -e /app/services/chat-inference \
      -e /app/services/user-history \
      -e /app/services/user-profile \
      -e /app/services/personalization

# 9. Expose your gateway port
EXPOSE 8000

# 10. Entrypoint: run your API Gateway
CMD ["uvicorn", "api_gateway_monolith.main:app", "--host", "0.0.0.0", "--port", "8000"]

# If you want to use a .env file, you can uncomment the line below
# CMD ["sh", "-c", "export MY_VAR=$(cat /app/.env) && uvicorn api_gateway_monolith.main:app --host 0.0.0.0 --port 8000"]
