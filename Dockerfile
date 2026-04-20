FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG PG_IMAGE=docker.m.daocloud.io/library/postgres:16-alpine

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg docker.io \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] http://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && PG_MAJOR="$(printf '%s' \"$PG_IMAGE\" | sed -nE 's#^.*/postgres:([0-9]+).*#\1#p')" \
    && test -n "$PG_MAJOR" \
    && apt-get install -y --no-install-recommends "postgresql-client-$PG_MAJOR" \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app

ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
