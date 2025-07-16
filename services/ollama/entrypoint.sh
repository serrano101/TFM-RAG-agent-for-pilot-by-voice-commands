#!/bin/bash
set -e

# Arranca el servidor Ollama en segundo plano
ollama serve &

# Espera a que el servidor esté listo
sleep 5

# Haz pull automático de los modelos que quieras
# ollama pull llama3
ollama pull mistral:instruct

# Espera a que termine el servidor
wait
