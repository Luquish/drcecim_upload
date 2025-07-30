# Usar imagen base de Python 3.11
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para el procesamiento de PDFs y Google Cloud
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    git \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de configuración y dependencias primero (para optimizar cache de Docker)
COPY requirements.txt setup.py README.md ./
COPY config/ ./config/
COPY services/ ./services/
COPY ui/ ./ui/

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .[ui]

# Copiar el resto de la aplicación
COPY streamlit_app.py ./
COPY .streamlit/ ./.streamlit/

# Crear directorios necesarios
RUN mkdir -p logs temp data/embeddings data/processed

# Configurar variables de entorno por defecto
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

# Exponer el puerto de Streamlit
EXPOSE 8501

# Comando de salud para verificar que la app está funcionando
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Comando para ejecutar la aplicación
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"] 