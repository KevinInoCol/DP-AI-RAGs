// Cliente del backend FastAPI. En desarrollo usamos el proxy /api de Vite.
const BASE = '/api'

export async function fetchSplitters() {
  const res = await fetch(`${BASE}/splitters`)
  if (!res.ok) throw new Error('No se pudo cargar el catálogo de splitters')
  const data = await res.json()
  return data.splitters
}

export async function splitText({ splitter, text, params }) {
  const res = await fetch(`${BASE}/split`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ splitter, text, params }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Error al dividir el texto')
  }
  return res.json()
}

export async function fetchLoaders() {
  const res = await fetch(`${BASE}/loaders`)
  if (!res.ok) throw new Error('No se pudo cargar el catálogo de loaders')
  const data = await res.json()
  return data.loaders
}

export async function loadDocument({ loader, file }) {
  const form = new FormData()
  form.append('loader', loader)
  form.append('file', file)
  const res = await fetch(`${BASE}/load`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Error al cargar el documento')
  }
  return res.json()
}

export async function fetchEmbedders() {
  const res = await fetch(`${BASE}/embedders`)
  if (!res.ok) throw new Error('No se pudo cargar el catálogo de embedders')
  const data = await res.json()
  return data.embedders
}

export async function buildIndex({ embedder, chunks, params }) {
  const res = await fetch(`${BASE}/index`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ embedder, chunks, params }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Error al indexar el documento')
  }
  return res.json()
}

export async function searchIndex({ query, top_k = 5 }) {
  const res = await fetch(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Error al buscar')
  }
  return res.json()
}

export async function fetchVectorStores() {
  const res = await fetch(`${BASE}/vectorstores`)
  if (!res.ok) throw new Error('No se pudo cargar el catálogo de vector stores')
  const data = await res.json()
  return data.vectorstores
}

export async function runBenchmark(payload) {
  const res = await fetch(`${BASE}/vectorstores/benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Error en el benchmark')
  }
  return res.json()
}

export async function extractFile(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/extract`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'No se pudo extraer el archivo')
  }
  return res.json()
}

export async function fetchPipeline() {
  const res = await fetch(`${BASE}/pipeline`)
  if (!res.ok) throw new Error('No se pudo cargar la descripción del pipeline')
  return res.json()
}

// Lee una respuesta SSE del backend: cada evento llega como una línea
// `data: {...}` y se pasa a `onEvent` a medida que llega.
async function readSse(res, onEvent, fallbackError) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || fallbackError)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop()
    for (const part of parts) {
      const line = part.trim()
      if (line.startsWith('data:')) onEvent(JSON.parse(line.slice(5)))
    }
  }
}

// Ingesta real con PDFs subidos desde el navegador (POST /ingest, SSE).
export async function ingestDocuments({ tenant, files, loader, ocrEngine, splitter, embedder, onEvent }) {
  const form = new FormData()
  form.append('tenant', tenant)
  for (const f of files) form.append('files', f)
  if (loader) form.append('loader', loader)
  if (ocrEngine) form.append('ocr_engine', ocrEngine)
  if (splitter) form.append('splitter', splitter)
  if (embedder) form.append('embedder', embedder)

  const res = await fetch(`${BASE}/ingest`, { method: 'POST', body: form })
  await readSse(res, onEvent, 'No se pudo iniciar la ingesta')
}

// PDFs de un bucket de GCS, para revisarlos antes de ingestar.
export async function listGcsPdfs({ bucket, prefix }) {
  const qs = new URLSearchParams({ bucket, prefix: prefix || '' })
  const res = await fetch(`${BASE}/gcs/pdfs?${qs}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'No se pudo leer el bucket')
  }
  return res.json()
}

// Ingesta real desde un bucket de GCS (POST /ingest/gcs, SSE).
export async function ingestFromGcs({ tenant, bucket, prefix, loader, ocrEngine, splitter, embedder, onEvent }) {
  const res = await fetch(`${BASE}/ingest/gcs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tenant,
      bucket,
      prefix: prefix || '',
      ...(ocrEngine && { ocr_engine: ocrEngine }),
      loader: loader || null,
      splitter: splitter || null,
      embedder: embedder || null,
    }),
  })
  await readSse(res, onEvent, 'No se pudo iniciar la ingesta desde GCS')
}

// Colecciones de tenants que ya existen en Qdrant (para reutilizarlas).
export async function fetchCollections() {
  const res = await fetch(`${BASE}/collections`)
  if (!res.ok) throw new Error('No se pudieron leer las colecciones de Qdrant')
  return res.json()
}

// Nombre final de la colección para un tenant (mismas reglas que la ingesta) y si
// ya existe; con `embedder` avisa si su dimensión no coincide.
export async function previewCollection({ tenant, embedder }) {
  const qs = new URLSearchParams({ tenant, ...(embedder && { embedder }) })
  const res = await fetch(`${BASE}/collections/preview?${qs}`)
  if (!res.ok) throw new Error('No se pudo calcular el nombre de la colección')
  return res.json()
}
