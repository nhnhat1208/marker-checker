FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY marker_checker_agent/ ./marker_checker_agent/

RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
