# Frontend-RAGs · Visualizador de Text Splitters (React + Vite)

UI para cargar un documento (pegando texto o subiendo un archivo), elegir una
técnica de **Text Splitter** de LlamaIndex desde el menú lateral, ajustar sus
parámetros y ver los chunks resultantes.

## Requisitos

- Node.js 18+
- El **Backend-RAGs** corriendo en `http://localhost:8005`

## Instalación y ejecución

```bash
cd Frontend-RAGs
npm install
npm run dev
```

Abre http://localhost:5174

> El frontend habla con el backend a través del proxy `/api` configurado en
> `vite.config.js` (apunta a `http://localhost:8005`).

## Funcionalidades

- 📂 Menú lateral con los splitters **agrupados por 🟢 Sin API Key / 🔵 Con API Key**
- 📄 Entrada por **texto pegado** o **archivo subido** (.txt, .md, .pdf, código…)
- 🎛️ Controles de parámetros dinámicos por técnica
- ✂️ Visualización de chunks en tarjetas de colores con tokens/caracteres
- 📊 Estadísticas globales (nº de chunks, tokens totales, promedios)
