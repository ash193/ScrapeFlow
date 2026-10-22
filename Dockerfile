
# Use an official Python 3.13 image.
# The slim variant is smaller than the standard image.
FROM python:3.13-slim

# Prevent Python from writing .pyc cache files.
ENV PYTHONDONTWRITEBYTECODE=1

# Show Python logs immediately instead of buffering them.
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container.
WORKDIR /app

# Copy dependencies first to improve Docker build caching.
COPY requirements.txt .

# Install the project's Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source into the container.
COPY . .

# Document the port used by FastAPI.
EXPOSE 8000

# Start FastAPI when the container runs.
# Assumes the FastAPI instance is named "app" in app/main.py.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
