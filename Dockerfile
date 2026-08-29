FROM python:3.10-slim

# Install system dependencies, Qt/X11 graphics libraries, and Tesseract OCR
RUN apt-get update && apt-get install -y \
    wget \
    potrace \
    xvfb \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-randr0 \
    libxcb-xfixes0 \
    libx11-xcb1 \
    libfontconfig1 \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN wget -O /tmp/oda.deb "https://github.com/nalinmittal2009-lab/jpg-to-dwg-converter/releases/download/v1.0/ODAFileConverter.deb" \
    && apt-get update && apt-get install -y -f /tmp/oda.deb \
    && rm /tmp/oda.deb

RUN TARGET_DIR=$(ls -d /usr/bin/ODAFileConverter_* | head -n 1) && \
    echo '#!/bin/bash' > /usr/local/bin/ODAFileConverter && \
    echo "exec xvfb-run -a $TARGET_DIR/ODAFileConverter \"\$@\"" >> /usr/local/bin/ODAFileConverter && \
    chmod +x /usr/local/bin/ODAFileConverter

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV XDG_RUNTIME_DIR=/tmp/runtime-root

EXPOSE 8000
CMD ["sh", "-c", "xvfb-run -a uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
