# 1. Imagen base de Python ligera
FROM python:3.9-slim

# 2. Variables de entorno para que Python no genere archivos temporales
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 3. Instalamos dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# 4. Copiamos los requerimientos e instalamos las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. DESCARGA DEL MODELO EN ESPAÑOL (Paso crítico)
# Esto descarga el "cerebro" dentro de la imagen para que no falle al arrancar
RUN python -m spacy download es_core_news_lg

# 6. Copiamos el resto del código (main.py)
COPY . .

# 7. Exponemos el puerto 8080 (Estándar para Render/Cloud Run)
EXPOSE 8080

# 8. Comando de arranque de la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]