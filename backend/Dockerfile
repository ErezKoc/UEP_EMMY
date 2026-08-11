FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for OpenAI Whisper audio decoding)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set python path to allow running modules from /app
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start FastAPI application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
