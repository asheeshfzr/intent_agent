# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system deps for popular Python libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Default to running the API; other processes (mocks) are launched via docker-compose with different commands
ENV AGENT_HOST=0.0.0.0
EXPOSE 8000 9000 9010
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
