FROM pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime

# Configurar variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TTS_HOME=/root/.local/share/tts

# Crear directorio de trabajo
WORKDIR /app

# Dependencias del sistema (ffmpeg, espeak para algunos modelos TTS)
RUN apt-get update && \
    apt-get install -y python3 python3-pip ffmpeg curl espeak-ng libsndfile1 git && \
    rm -rf /var/lib/apt/lists/*

# Copiar los archivos de requirements e instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY src/ ./src/

# Exponer puerto para servidor TTS
EXPOSE 8000

# Un solo worker para evitar doble inicialización
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]