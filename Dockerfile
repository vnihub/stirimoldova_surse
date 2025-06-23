FROM python:3.11-slim

# Install system dependencies for Playwright and Chromium
RUN apt-get update && apt-get install -y \
    curl unzip wget libnss3 libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libxcb-dri3-0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 \
    fonts-liberation libappindicator3-1 lsb-release \
    && apt-get clean

WORKDIR /app

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt && echo "force rebuild"

# Install Chromium for Playwright
RUN pip install playwright && playwright install chromium

CMD ["python", "-u", "run.py"]