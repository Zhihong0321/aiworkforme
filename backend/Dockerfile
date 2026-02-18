# Start with a Python 3.12 base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
# Add a default unprivileged user.
RUN useradd --no-create-home appuser

COPY . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 9555

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9555"]
