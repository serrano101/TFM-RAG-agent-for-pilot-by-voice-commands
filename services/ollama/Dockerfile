
# Dockerfile para Ollama con entrypoint automático
FROM ollama/ollama:latest
# Dependencias para TLS y readiness
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*
# Copia el entrypoint personalizado
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 11434

# Healthcheck básico
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:11434/api/version || exit 1

ENTRYPOINT ["/usr/bin/env", "bash", "/entrypoint.sh"]
