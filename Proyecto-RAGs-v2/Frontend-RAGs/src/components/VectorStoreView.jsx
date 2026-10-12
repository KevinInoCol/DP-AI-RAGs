import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Gauge, Loader2, Play, Timer, Hammer, Target } from 'lucide-react'
import { runBenchmark } from '../api'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

const SAMPLE_DOC = `La garantía del producto cubre defectos de fábrica durante 12 meses.

Para hacer válida la garantía, conserva la boleta de compra y contacta al centro de servicio autorizado.

El horario de atención al cliente es de lunes a viernes, de 9:00 a 18:00.

Los envíos a provincia demoran entre 3 y 5 días hábiles.

Aceptamos pagos con tarjeta de crédito, débito y transferencia bancaria.

Las devoluciones se aceptan dentro de los 7 días posteriores a la compra.`

const SAMPLE_QUERIES = `¿Cuánto dura la garantía?
¿Cómo pago mi pedido?
¿En cuánto tiempo llega a provincia?`

function KindBadge({ kind }) {
  if (kind === 'ann') {
    return (
      <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
        ANN · aproximado
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
      Exacto · fuerza bruta
    </Badge>
  )
}

function Metric({ icon: Icon, label, value, unit, highlight }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <Icon className="size-3" /> {label}
      </span>
      <span className={cn('font-mono text-lg font-semibold tabular-nums', highlight && 'text-primary')}>
        {value}
        {unit && <span className="ml-0.5 text-xs font-normal text-muted-foreground">{unit}</span>}
      </span>
    </div>
  )
}

// Pestaña de Vector Store: benchmark Fuerza Bruta vs. ANN.
export default function VectorStoreView({ stores, embedders, selected }) {
  const [embedder, setEmbedder] = useState('')
  const [embedParams, setEmbedParams] = useState({})
  const [doc, setDoc] = useState(SAMPLE_DOC)
  const [queries, setQueries] = useState(SAMPLE_QUERIES)
  const [syntheticScale, setSyntheticScale] = useState(5000)
  const [topK, setTopK] = useState(5)
  const [storeParams, setStoreParams] = useState({ M: 16, ef_search: 64 })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Params por defecto de un embedder (cada proveedor tiene sus propias opciones
  // de dimensión: Gemini 768/1536/3072, OpenAI 512/1024/1536).
  function defaultsFor(item) {
    const defaults = {}
    for (const p of item?.params || []) defaults[p.name] = p.default
    return defaults
  }

  // Embedder inicial: el que el backend resolvería en automático (el primero con
  // API key), no el primero del catálogo.
  useEffect(() => {
    if (!embedders?.length) return
    const pick =
      embedders.find((e) => e.is_default) || embedders.find((e) => e.available) || embedders[0]
    setEmbedder(pick.key)
    setEmbedParams(defaultsFor(pick))
  }, [embedders])

  // Al cambiar de proveedor hay que resetear sus params: una dimensión válida en
  // uno puede no existir en el otro.
  function handleEmbedderChange(key) {
    setEmbedder(key)
    setEmbedParams(defaultsFor(embedders?.find((e) => e.key === key)))
    setResult(null)
  }

  const selectedEmbedder = useMemo(
    () => embedders?.find((e) => e.key === embedder) || null,
    [embedders, embedder],
  )
  const embedderUnavailable = selectedEmbedder?.available === false

  // Params del motor ANN (HNSW de Qdrant), tomados del catálogo.
  const hnsw = useMemo(() => stores?.find((s) => s.key === 'qdrant_hnsw'), [stores])

  function chunkCount(raw) {
    return raw.split(/\n\s*\n/).map((c) => c.trim()).filter(Boolean).length
  }

  async function handleRun() {
    const chunks = doc.split(/\n\s*\n/).map((c) => c.trim()).filter(Boolean)
    const qs = queries.split('\n').map((q) => q.trim()).filter(Boolean)
    if (!chunks.length || !qs.length || !embedder) return
    setLoading(true)
    setError(null)
    try {
      const data = await runBenchmark({
        embedder,
        embed_params: embedParams,
        chunks,
        queries: qs,
        top_k: Number(topK),
        synthetic_scale: Number(syntheticScale),
        store_params: storeParams,
      })
      setResult(data)
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const okResults = result?.results.filter((r) => r.status === 'ok') || []
  const fastest = okResults.length
    ? Math.min(...okResults.map((r) => r.avg_search_ms))
    : null

  return (
    <div className="flex flex-col gap-5">
      {selected && (
        <Card className="gap-3 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold">{selected.name}</h2>
            <KindBadge kind={selected.kind} />
            <span className="font-mono text-xs text-muted-foreground">{selected.engine}</span>
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground">{selected.description}</p>
        </Card>
      )}

      {/* Configuración del benchmark */}
      <Card className="gap-4 p-5">
        <h2 className="text-sm font-semibold">Configuración de la comparación</h2>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">Modelo de embedding</Label>
            <Select value={embedder} onValueChange={handleEmbedderChange}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {embedders?.map((e) => (
                  <SelectItem key={e.key} value={e.key} disabled={e.available === false}>
                    {e.name}
                    {e.available === false && ' · falta key'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">
              Vectores sintéticos (escala del índice)
            </Label>
            <Input
              type="number"
              className="font-mono"
              value={syntheticScale}
              min={0}
              max={50000}
              step={1000}
              onChange={(e) => setSyntheticScale(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">top_k</Label>
            <Input
              type="number"
              className="font-mono"
              value={topK}
              min={1}
              max={50}
              step={1}
              onChange={(e) => setTopK(e.target.value)}
            />
          </div>
          {hnsw?.params.map((p) => (
            <div key={p.name} className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground">{p.label}</Label>
              <Input
                type="number"
                className="font-mono"
                value={storeParams[p.name] ?? p.default}
                min={p.min}
                max={p.max}
                step={p.step}
                onChange={(e) =>
                  setStoreParams((prev) => ({ ...prev, [p.name]: parseInt(e.target.value, 10) }))
                }
              />
            </div>
          ))}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">
              Documento — {chunkCount(doc)} chunks (por párrafo)
            </Label>
            <Textarea
              value={doc}
              onChange={(e) => setDoc(e.target.value)}
              rows={8}
              className="resize-y font-mono text-[13px] leading-relaxed"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">Consultas (una por línea)</Label>
            <Textarea
              value={queries}
              onChange={(e) => setQueries(e.target.value)}
              rows={8}
              className="resize-y font-mono text-[13px] leading-relaxed"
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {embedderUnavailable ? (
              <span className="text-destructive">
                Falta {selectedEmbedder.requires_env} en el .env del backend.
              </span>
            ) : (
              'El índice se rellena con vectores aleatorios para que el trade-off sea visible.'
            )}
          </span>
          <Button onClick={handleRun} disabled={loading || embedderUnavailable}>
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Comparando…
              </>
            ) : (
              <>
                <Play className="size-4" /> Ejecutar comparación
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

      {result && (
        <>
          <div className="flex flex-wrap gap-x-5 gap-y-1 rounded-lg border border-border bg-card px-4 py-3 font-mono text-xs text-muted-foreground">
            <span>{result.num_vectors.toLocaleString()} vectores</span>
            <span>{result.num_real_chunks} chunks reales</span>
            <span>{result.dimension} dims</span>
            <span>{selectedEmbedder?.model || result.embedder}</span>
            <span>top_k={result.top_k}</span>
            <span>{result.num_queries} queries</span>
          </div>

          <div className="flex flex-col gap-3">
            {result.results.map((r) => (
              <Card
                key={r.key}
                className={cn(
                  'gap-4 p-5',
                  r.kind === 'ann' ? 'border-l-4 border-l-primary' : 'border-l-4 border-l-emerald-500/60',
                )}
              >
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="font-semibold">{r.name}</h3>
                  <KindBadge kind={r.kind} />
                  <span className="font-mono text-xs text-muted-foreground">{r.engine}</span>
                </div>

                {r.status === 'error' ? (
                  <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                    <span>{r.message}</span>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-4">
                      <Metric icon={Hammer} label="Construir índice" value={r.build_ms} unit="ms" />
                      <Metric
                        icon={Timer}
                        label="Búsqueda (prom.)"
                        value={r.avg_search_ms}
                        unit="ms"
                        highlight={r.avg_search_ms === fastest}
                      />
                      <Metric
                        icon={Target}
                        label="Recall@k"
                        value={`${(r.recall * 100).toFixed(1)}%`}
                        highlight={r.recall < 1}
                      />
                    </div>
                    {/* Barra de recall */}
                    <div className="flex items-center gap-2">
                      <Gauge className="size-3.5 text-muted-foreground" />
                      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                        <span
                          className={cn('block h-full rounded-full', r.recall < 1 ? 'bg-primary' : 'bg-emerald-500')}
                          style={{ width: `${r.recall * 100}%` }}
                        />
                      </span>
                    </div>
                  </>
                )}
              </Card>
            ))}
          </div>

          {/* Resultados de la 1ª query (baseline) */}
          {okResults[0]?.hits?.length > 0 && (
            <Card className="gap-3 p-5">
              <h3 className="text-sm font-semibold">
                Top-{result.top_k} para “{result.query}” — {okResults[0].name}
              </h3>
              <div className="flex flex-col gap-2">
                {okResults[0].hits.map((h) => (
                  <div
                    key={h.rank}
                    className="flex items-start gap-3 rounded-md border border-border bg-muted/30 px-3 py-2"
                  >
                    <span className="font-mono text-xs text-muted-foreground">#{h.rank}</span>
                    <span className="font-mono text-xs text-muted-foreground">{h.score}</span>
                    <span
                      className={cn(
                        'flex-1 text-[13px]',
                        h.kind === 'synthetic' && 'italic text-muted-foreground',
                      )}
                    >
                      {h.text}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
