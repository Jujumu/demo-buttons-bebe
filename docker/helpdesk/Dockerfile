# Sellable inbox + helpdesk package. Secrets stay out of the image.
# Mount .env or pass runtime env. See CONNECT.md.
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN groupadd --gid 10001 helpdesk \
    && useradd --uid 10001 --gid 10001 --home /data --create-home helpdesk \
    && mkdir -p /data \
    && chown helpdesk:helpdesk /data

COPY --chown=helpdesk:helpdesk console-src/inbox /app/console-src/inbox
COPY --chown=helpdesk:helpdesk console-src/helpdesk-agent /app/console-src/helpdesk-agent

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INBOX_HOST=0.0.0.0 \
    INBOX_PORT=8766 \
    SHOPIFY_MUTATIONS_ENABLED=0 \
    SHOPIFY_API_VERSION=2026-07 \
    GORGIAS_BRIDGE_ENABLED=0 \
    HELPDESK_OUTBOUND_ENABLED=0 \
    HELPDESK_STORE_FILE=/data/intake_tickets.json \
    HELPDESK_SEEN_FILE=/data/seen_messages.json

EXPOSE 8766

USER helpdesk

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/health')"

CMD ["python3", "-u", "console-src/inbox/review_server.py"]
