# ---------- Frontend build (multi-stage) ----------
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---------- Backend runtime ----------
FROM python:3.12-slim
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add a default unprivileged user.
RUN useradd --no-create-home appuser

# Copy backend code
COPY backend/ .

# Copy built frontend assets into the location FastAPI serves from
COPY --from=frontend-build /app/frontend/dist ./frontend-dist

# Change ownership of the application directory to the non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
