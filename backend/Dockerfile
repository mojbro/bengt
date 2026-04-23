FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 3501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3501"]
