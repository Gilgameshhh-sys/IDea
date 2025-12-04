# 1. CAMBIO CLAVE: Usamos la imagen COMPLETA (sin "-slim")
# Esto trae todos los compiladores necesarios para 'blis' y 'spacy'
FROM python:3.9

# 2. Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 3. Actualizamos pip (el instalador) para evitar errores de versiones viejas
RUN pip install --upgrade pip

# 4. Copiamos los requerimientos
COPY requirements.txt .

# 5. Instalamos las librerías
# La imagen completa ya tiene lo necesario para compilar 'blis'
RUN pip install --no-cache-dir -r requirements.txt

# 6. Descarga del modelo en Español
RUN python -m spacy download es_core_news_md

# 7. Copiamos el código
COPY . .

# 8. Exponemos el puerto
EXPOSE 8080

# 9. Arrancamos
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

