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
