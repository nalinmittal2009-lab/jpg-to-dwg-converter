FROM python:3.10-slim

# Install system dependencies, font config, and UI libraries required by ODA
RUN apt-get update && apt-get install -y \
    wget \
    potrace \
    xvfb \
    libgl1 \
    libglib2.0-0 \
    libxkbcommon0 \
    libxcb-cursor0 \
    libfontconfig1 \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dynamically scrape and install the latest ODA File Converter package
RUN apt-get update \
    && ODA_FILE=$(wget -qO- https://www.opendesign.com/guestfiles/oda_file_converter | grep -oE 'ODAFileConverter_QT[a-zA-Z0-9_.]+\.deb' | head -n 1) \
    && echo "Found installer: $ODA_FILE" \
    && wget -O /tmp/oda.deb "https://www.opendesign.com/guestfiles/get?filename=$ODA_FILE" \
    && apt-get install -y -f /tmp/oda.deb \
    && rm /tmp/oda.deb

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000
CMD ["sh", "-c", "xvfb-run -a uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
