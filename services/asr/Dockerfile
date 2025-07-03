# Seleccionar la imagen base de Ubuntu 22.04
FROM ubuntu:22.04


# Instalar Python, pip y ffmpeg; y limpieza para reducir el tamaño de la imagen
RUN apt-get update && \
    apt-get install -y python3 python3-pip ffmpeg libnvrtc11.6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app


# Copiar los archivos de requirements e instalar dependencias (excepto torch con CUDA)
COPY requirements.txt ./
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Instalar torch con soporte CUDA 11.8 desde el índice oficial de PyTorch --> Para detectar si hay GPU
RUN pip3 install torch==2.1.0+cu118 --index-url https://download.pytorch.org/whl/cu118

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto por defecto de Uvicorn/FastAPI
EXPOSE 8000

# Comando para lanzar el servidor
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

