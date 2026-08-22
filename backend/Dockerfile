FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for OpenAI Whisper audio decoding)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
# Whisper needs PyTorch, but this container runs inference on CPU. Installing
# the official CPU wheel first prevents pip from pulling several gigabytes of
# unused NVIDIA/CUDA runtime packages.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Keep recommendation dependencies in a separate layer so adding one does not
# invalidate the much larger Whisper/PyTorch installation above.
COPY requirements-recsys.txt .
RUN pip install --no-cache-dir -r requirements-recsys.txt

# Copy the rest of the application
COPY . .

# Set python path to allow running modules from /app
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start FastAPI application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
