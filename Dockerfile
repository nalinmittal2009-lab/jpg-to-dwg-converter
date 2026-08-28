FROM python:3.10-slim

# Install system dependencies, potrace, xvfb, and wget
RUN apt-get update && apt-get install -y \
    wget \
    potrace \
    xvfb \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Download the ODA File Converter .deb package directly inside the container
RUN wget -O /tmp/oda.deb https://www.opendesign.com/guestfiles/oda_file_converter/download?filename=ODAFileConverter_Ubuntu22.04_amd64.deb || \
    wget -O /tmp/oda.deb https://www.opendesign.com/guestfiles/oda_file_converter

# Install the downloaded DEB package
RUN apt-get update && apt-get install -y /tmp/oda.deb || true \
    && rm /tmp/oda.deb

# Create symlink for execution
RUN ln -s /usr/bin/ODAFileConverter /usr/local/bin/ODAFileConverter || true

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy main application code
COPY app.py .

EXPOSE 8000

CMD ["sh", "-c", "xvfb-run -a uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
