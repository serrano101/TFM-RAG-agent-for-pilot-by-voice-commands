# Seleccionar la imagen base de Ubuntu 22.04
FROM ubuntu:22.04


# Instalar Python, pip y ffmpeg; y limpieza para reducir el tamaño de la imagen
RUN apt-get update && \
    apt-get install -y python3 python3-pip ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app


# Copiar los archivos de requirements e instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Establecer la variable de entorno PYTHONPATH
ENV PYTHONPATH=/app

# Comando para lanzar el servidor
CMD ["python3", "src/presentation/watcher.py"]

