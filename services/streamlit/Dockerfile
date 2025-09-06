# Imagen base ligera de Python 3.10
FROM python:3.10-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de dependencias
COPY requirements.txt ./

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código fuente de la app
COPY src/ ./src/

# Expone el puerto por defecto de Streamlit
EXPOSE 8501

# Establecer la variable de entorno PYTHONPATH
ENV PYTHONPATH=/app

# Comando por defecto: lanza la app de Streamlit en modo servidor accesible desde cualquier IP
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
