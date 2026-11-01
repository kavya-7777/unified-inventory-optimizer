FROM python:3.11-slim

WORKDIR /app

# Every dependency (OR-Tools, NumPy/SciPy, PyMySQL, cryptography, bcrypt) ships as a binary
# wheel, so no compilers or system libraries are needed.
# Test/lint tools are only needed locally and in CI: docker-compose.yml sets INSTALL_DEV=true.
ARG INSTALL_DEV=false
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 8000

# Apply database migrations, then serve. Render sets $PORT; locally it defaults to 8000.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
