import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, FileText, Scissors } from 'lucide-react'
import { splitText, extractFile, loadDocument } from '../api'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import DocumentInput from './DocumentInput'
import ParamControls from './ParamControls'
import ChunkViewer from './ChunkViewer'

const SAMPLE = `LlamaIndex es un framework para construir aplicaciones RAG.
El chunking (o segmentación) es un paso clave: divide los documentos en
fragmentos más pequeños llamados "nodes".

Existen varias técnicas. El SentenceSplitter intenta no romper oraciones.
El TokenTextSplitter corta por número de tokens. Los splitters semánticos
usan embeddings para detectar cambios de tema y cortar en el punto óptimo.

Elegir el splitter correcto mejora mucho la calidad de la recuperación.`

// Algunos splitters de LangChain esperan un formato concreto (Markdown, HTML,
// JSON). Si el usuario no ha tocado el texto de ejemplo, se cambia por uno que
// sirva para la técnica elegida.
const SAMPLES_BY_SPLITTER = {
  lc_markdown_header: `# Manual de RAG

Guía corta sobre la ingesta de documentos.

## Chunking

El chunking divide los documentos en fragmentos más pequeños.

### Por encabezados

Cada sección del Markdown queda en su propio chunk, con sus encabezados como metadata.

## Embeddings

Cada chunk se convierte en un vector y se guarda en Qdrant.`,
  lc_html_header: `<html><body>
<h1>Manual de RAG</h1>
<p>Guía corta sobre la ingesta de documentos.</p>
<h2>Chunking</h2>
<p>El chunking divide los documentos en fragmentos más pequeños.</p>
<h3>Por encabezados</h3>
<p>Cada sección del HTML queda en su propio chunk, con sus encabezados como metadata.</p>
<h2>Embeddings</h2>
<p>Cada chunk se convierte en un vector y se guarda en Qdrant.</p>
</body></html>`,
  lc_json: JSON.stringify(
    {
      pipeline: {
        nombre: 'Ingesta de PDFs',
        etapas: {
          validacion: { descripcion: 'Comprueba si el PDF trae texto nativo', usa_api: false },
          ocr: { descripcion: 'Extrae texto de páginas escaneadas', motores: ['tesseract', 'llamaparse'] },
          chunking: { descripcion: 'Divide el texto en fragmentos', tamano_tokens: 512, solape: 64 },
          embeddings: { descripcion: 'Convierte cada chunk en un vector', proveedores: ['gemini', 'openai'] },
        },
      },
      vector_store: { motor: 'Qdrant', indice: 'HNSW', metrica: 'coseno' },
    },
    null,
    2,
  ),
  lc_code: `class Chunker:
    """Divide un texto en fragmentos."""

    def __init__(self, size: int = 512, overlap: int = 64):
        self.size = size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        step = self.size - self.overlap
        return [text[i:i + self.size] for i in range(0, len(text), step)]


def main():
    chunker = Chunker(size=100)
    print(chunker.split("hola " * 100))`,
}
SAMPLES_BY_SPLITTER.code = SAMPLES_BY_SPLITTER.lc_code

const ALL_SAMPLES = new Set([SAMPLE, ...Object.values(SAMPLES_BY_SPLITTER)])

// Pestaña de Text Splitters (chunking): texto -> nodes.
// La extracción de archivos reutiliza el Document Loader seleccionado en la
// otra pestaña (prop `loader`), encadenando el pipeline: Loader -> Splitter.
export default function SplitterView({ selected, loader }) {
  const [text, setText] = useState(SAMPLE)
  const [params, setParams] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Al cambiar de splitter, resetear parámetros a sus valores por defecto.
  useEffect(() => {
    if (!selected) return
    const defaults = {}
    for (const p of selected.params) defaults[p.name] = p.default
    setParams(defaults)
    setResult(null)
    setError(null)
    setText((t) => (ALL_SAMPLES.has(t) ? SAMPLES_BY_SPLITTER[selected.key] ?? SAMPLE : t))
  }, [selected])

  async function handleSplit() {
    if (!selected || !text.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await splitText({ splitter: selected.key, text, params })
      setResult(data)
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  // ¿El loader seleccionado acepta este tipo de archivo?
  function loaderAcceptsFile(file) {
    if (!loader) return false
    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
    return loader.accepts?.includes(ext)
  }

  async function handleFile(file) {
    setError(null)
    try {
      if (loaderAcceptsFile(file)) {
        // Pipeline real: extraer con el Document Loader elegido en la otra pestaña.
        const data = await loadDocument({ loader: loader.key, file })
        setText(data.documents.map((d) => d.text).join('\n\n'))
      } else {
        // Fallback para archivos que el loader no soporta (.txt, .md, código…).
        const data = await extractFile(file)
        setText(data.text)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  if (!selected) return null

  return (
    <div className="flex flex-col gap-5">
      <Card className="gap-4 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">{selected.name}</h2>
          {selected.framework_name && (
            <Badge variant="outline" className="font-mono text-[11px]">
              {selected.framework_name}
            </Badge>
          )}
          {selected.requires_api_key ? (
            <Badge variant="outline" className="border-sky-500/30 bg-sky-500/10 text-sky-400">
              Con API Key
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
            >
              Sin API Key
            </Badge>
          )}
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{selected.description}</p>
        <ParamControls
          params={selected.params}
          values={params}
          onChange={(name, value) => setParams((p) => ({ ...p, [name]: value }))}
        />
      </Card>

      {loader && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-[13px]">
          <span className="flex items-center gap-1.5">
            <FileText className="size-4 text-primary" />
            Al subir un archivo se extrae con <b className="font-medium">{loader.name}</b>
          </span>
          <ArrowRight className="size-4 text-primary" />
          <span className="flex items-center gap-1.5">
            <Scissors className="size-4 text-primary" />
            luego se divide con <b className="font-medium">{selected.name}</b>
          </span>
          <span className="w-full text-xs text-muted-foreground">
            (cambia el loader en la sección “Document Loaders”)
          </span>
        </div>
      )}

      <DocumentInput
        text={text}
        onChangeText={setText}
        onFile={handleFile}
        onRun={handleSplit}
        loading={loading}
      />

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <ChunkViewer result={result} loading={loading} />
    </div>
  )
}
