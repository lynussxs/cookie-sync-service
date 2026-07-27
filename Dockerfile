FROM mcr.microsoft.com/playwright/python:v1.40.0-focal
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps
COPY . .
CMD ["python", "cookie_sync_service.py"]
