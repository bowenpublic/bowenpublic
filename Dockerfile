FROM python:3.11-slim

WORKDIR /app

# Install curl for downloading files
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# PyTorch, CPU-only build. The server has no GPU, and the default build pulls
# about 2.7 GB of Nvidia libraries that are never loaded. Installed in its own
# layer, before requirements.txt is copied, so a requirements change does not
# download it again. sentence-transformers then finds torch already installed.
# 2.15.0 is the version the default install resolved to on 13 Nov 2026.
RUN pip install --no-cache-dir torch==2.15.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
COPY backend/ ./backend/

# Create embeddings directory and download from GitHub Release
ARG DATA_RELEASE=v1.1-data
RUN mkdir -p data/embeddings
RUN curl -fL -o data/embeddings/embeddings.npy https://github.com/bowenpublic/bowenpublic/releases/download/${DATA_RELEASE}/embeddings.npy
RUN curl -fL -o data/embeddings/metadata.json https://github.com/bowenpublic/bowenpublic/releases/download/${DATA_RELEASE}/metadata.json
RUN curl -fL -o data/embeddings/config.json https://github.com/bowenpublic/bowenpublic/releases/download/${DATA_RELEASE}/config.json

# Expose port
EXPOSE 8000

# Run the app
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
