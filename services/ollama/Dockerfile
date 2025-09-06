
# Dockerfile para Ollama con entrypoint automático
FROM ollama/ollama:latest

# Copia el entrypoint personalizado
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 11434

ENTRYPOINT ["/entrypoint.sh"]
