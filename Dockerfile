FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8000

# Start the application
CMD ["gunicorn", "Blood.Backend.wsgi:application", "--bind", "0.0.0.0:8000"]
