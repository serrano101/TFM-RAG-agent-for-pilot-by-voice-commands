#!/bin/bash
set -e

# Arranca el servidor Ollama en segundo plano
ollama serve &

# Espera a que el servidor esté listo
sleep 5


# Lee el modelo a descargar desde config.yaml (clave: LLM.OLLAMA)
# MODEL=$(python3 -c "import yaml; f=open('/app/config.yaml'); print(yaml.safe_load(f)['LLM']['OLLAMA'])" 2>/dev/null)

# echo "Descargando modelo Ollama: $MODEL"
ollama pull "mistral:instruct"

# Espera a que termine el servidor
wait
