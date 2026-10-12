import { useEffect, useState } from 'react'
import { AlertTriangle, Boxes, Cpu, KeyRound, Loader2, Ruler, Search, Sparkles } from 'lucide-react'
import { buildIndex, searchIndex } from '../api'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import ParamControls from './ParamControls'
import StatGrid from './StatGrid'
import { chunkColor } from '@/lib/palette'

const SAMPLE = `La garantía del producto cubre defectos de fábrica durante 12 meses.

Para hacer válida la garantía, conserva la boleta de compra y contacta al centro de servicio autorizado.

El horario de atención al cliente es de lunes a viernes, de 9:00 a 18:00.

Los envíos a provincia demoran entre 3 y 5 días hábiles.`

// Pestaña de Embeddings (indexación): documento -> chunks -> vectores -> índice
// consultable. Cada párrafo (separado por línea en blanco) es un chunk.
export default function EmbedderView({ selected }) {
  const [text, setText] = useState(SAMPLE)
  const [params, setParams] = useState({})
  const [indexInfo, setIndexInfo] = useState(null)
  const [indexing, setIndexing] = useState(false)
  const [query, setQuery] = useState('¿Cuánto dura la garantía?')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(null)

  // Al cambiar de embedder: resetear params por defecto y limpiar índice/resultados.
  useEffect(() => {
    if (!selected) return
    const defaults = {}
    for (const p of selected.params) defaults[p.name] = p.default
    setParams(defaults)
    setIndexInfo(null)
    setResults(null)
    setError(null)
  }, [selected])

  function splitChunks(raw) {
    return raw
      .split(/\n\s*\n/)
      .map((c) => c.trim())
      .filter(Boolean)
  }

  async function handleIndex() {
    if (!selected) return
    const chunks = splitChunks(text)
    if (!chunks.length) return
    setIndexing(true)
    setError(null)
    setResults(null)
    try {
      const data = await buildIndex({ embedder: selected.key, chunks, params })
      setIndexInfo(data)
    } catch (e) {
      setError(e.message)
      setIndexInfo(null)
    } finally {
      setIndexing(false)
    }
  }

  async function handleSearch() {
    if (!query.trim() || !indexInfo) return
    setSearching(true)
    setError(null)
    try {
      const data = await searchIndex({ query, top_k: 5 })
      setResults(data)
    } catch (e) {
      setError(e.message)
      setResults(null)
    } finally {
      setSearching(false)
    }
  }

  if (!selected) return null

  // El backend nos dice si la API key de este proveedor está presente.
  const available = selected.available !== false
  const chunkCount = splitChunks(text).length

  return (
    <div className="flex flex-col gap-5">
      {/* Info del embedder */}
      <Card className="gap-4 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">{selected.name}</h2>
          {available ? (
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
            >
              <KeyRound className="size-3" /> {selected.requires_env} lista
            </Badge>
          ) : (
            <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive">
              <KeyRound className="size-3" /> Falta {selected.requires_env}
            </Badge>
          )}
          {selected.is_default && (
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              Por defecto
            </Badge>
          )}
          <Badge variant="secondary" className="font-normal">
            {selected.asymmetric ? 'Asimétrico (doc ≠ query)' : 'Simétrico (doc = query)'}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Cpu className="size-3.5" /> Proveedor:{' '}
            <span className="font-mono">{selected.provider}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <Sparkles className="size-3.5" /> Modelo:{' '}
            <span className="font-mono">{selected.model}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <Ruler className="size-3.5" /> Nativo:{' '}
            <span className="font-mono">{selected.native_dimension} dims</span>
          </span>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{selected.description}</p>
        <ParamControls
          params={selected.params}
          values={params}
          onChange={(name, value) => setParams((p) => ({ ...p, [name]: value }))}
        />
      </Card>

      {!available && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>
            Este modelo necesita <span className="font-mono">{selected.requires_env}</span> en el{' '}
            <span className="font-mono">.env</span> del backend.{' '}
            <a
              href={selected.api_key_url}
              target="_blank"
              rel="noreferrer"
              className="underline hover:no-underline"
            >
              Conseguir la key
            </a>
            . Mientras tanto, elige otro embedder en el menú lateral.
          </span>
        </div>
      )}

      {/* Documento a indexar */}
      <Card className="gap-0 p-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">Documento a indexar</h2>
          <span className="font-mono text-xs text-muted-foreground">
            {chunkCount} chunk{chunkCount === 1 ? '' : 's'} (por párrafo)
          </span>
        </div>
        <div className="p-5">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Pega el documento. Cada párrafo (separado por una línea en blanco) es un chunk."
            rows={8}
            className="resize-y font-mono text-[13px] leading-relaxed"
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3">
          <span className="text-xs text-muted-foreground">
            {selected.asymmetric
              ? 'Se embebe cada chunk como documento (retrieval asimétrico)'
              : 'Modelo simétrico: documento y query se embeben igual'}
          </span>
          <Button onClick={handleIndex} disabled={indexing || !chunkCount || !available}>
            {indexing ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Indexando…
              </>
            ) : (
              <>
                <Boxes className="size-4" /> Indexar documento
              </>
            )}
          </Button>
        </div>
      </Card>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {indexInfo && (
        <>
          <StatGrid
            stats={[
              { label: 'Chunks indexados', value: indexInfo.num_chunks },
              { label: 'Dimensión del vector', value: indexInfo.dimension },
              { label: 'Modelo', value: selected.model },
            ]}
          />

          {/* Consulta al índice */}
          <Card className="gap-0 p-0">
            <div className="border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">Consultar el índice</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2 p-5">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Escribe una pregunta…"
                className="min-w-0 flex-1"
              />
              <Button onClick={handleSearch} disabled={searching || !query.trim()}>
                {searching ? (
                  <>
                    <Loader2 className="size-4 animate-spin" /> Buscando…
                  </>
                ) : (
                  <>
                    <Search className="size-4" /> Buscar
                  </>
                )}
              </Button>
            </div>
          </Card>
        </>
      )}

      {results && (
        <div className="flex flex-col gap-3">
          {results.num_results === 0 ? (
            <Card className="items-center gap-2 border-dashed py-12 text-center">
              <Search className="size-6 text-muted-foreground/60" />
              <p className="text-sm text-muted-foreground">Sin resultados.</p>
            </Card>
          ) : (
            results.results.map((r) => {
              const color = chunkColor(r.index)
              return (
                <Card
                  key={r.rank}
                  className="gap-3 overflow-hidden border-l-4 p-4"
                  style={{ borderLeftColor: color }}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="rounded-md px-2 py-0.5 font-mono text-xs font-semibold text-white"
                      style={{ backgroundColor: color }}
                    >
                      #{r.rank}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">
                      similitud {r.score}
                    </span>
                    <span className="ml-auto h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.max(0, Math.min(r.score, 1)) * 100}%`,
                          backgroundColor: color,
                        }}
                      />
                    </span>
                  </div>
                  <pre className="whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-3 font-mono text-[13px] leading-relaxed">
                    {r.text}
                  </pre>
                </Card>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
