# Comandos · RAG Toolkit (Proyecto-RAGs-v2)

Se usan **dos terminales**: una para el Backend y otra para el Frontend.
Primero se levanta el Backend y luego el Frontend.

---

## 1. Backend (FastAPI · puerto 8005)

### Primera vez

```bash
# Entramos a la carpeta del Backend
cd Backend-RAGs

# Creamos el Entorno Virtual (Python 3.12; evitar 3.14 por falta de wheels)
conda create -n RAG-Pipeline python=3.12

# Activamos el Entorno Virtual
conda activate RAG-Pipeline

# Instalamos las dependencias
pip install -r requirements.txt

# Creamos el .env a partir del ejemplo y le ponemos las API keys
cp .env.example .env
```

En el `.env` basta con **una** clave de embeddings (`GOOGLE_API_KEY` u
`OPENAI_API_KEY`). Solo hace falta para los splitters semánticos, la indexación y
la ingesta. Las demás claves (`QDRANT_*`, `LLAMA_CLOUD_API_KEY`, ...) son opcionales.

### Ejecutar

```bash
cd Backend-RAGs
conda activate RAG-Pipeline

# El puerto 8005 es obligatorio: el proxy del Frontend apunta ahí
uvicorn main:app --reload --port 8005
```

- API: http://localhost:8005
- Documentación interactiva: http://localhost:8005/docs
- Estado y claves cargadas: http://localhost:8005/health

### Tests

```bash
cd Backend-RAGs
conda activate RAG-Pipeline
pip install -r requirements-dev.txt   # solo la primera vez
python -m pytest tests -q
```

---

## 2. Frontend (React + Vite · puerto 5174)

### Primera vez

```bash
# Entramos a la carpeta del Frontend
cd Frontend-RAGs

# Instalamos las dependencias
npm install
```

### Ejecutar

```bash
cd Frontend-RAGs
npm run dev
```

- App: http://localhost:5174

### Compilar para producción (opcional)

```bash
cd Frontend-RAGs
npm run build     # genera dist/
npm run preview   # sirve dist/ para revisarlo
```

---

## Problemas comunes

| Síntoma | Causa / solución |
|---|---|
| El Frontend no carga los catálogos | El Backend no está corriendo o no está en el puerto **8005**. |
| `Address already in use` en el 8005 | Ya hay otro proceso en ese puerto: `lsof -i :8005` y ciérralo. |
| Error al instalar `tiktoken` o `tree-sitter` | Estás en Python 3.14. Usa el entorno con Python 3.12. |
| El splitter semántico da error de API key | Falta `GOOGLE_API_KEY` u `OPENAI_API_KEY` en `Backend-RAGs/.env`. |
| `NLTKTextSplitter` tarda la primera vez | Descarga el modelo `punkt_tab` (una sola vez). |
