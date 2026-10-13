// Panel "Ejecutar ingesta" al final del Pipeline: RESUMEN de lo elegido en el
// diagrama (fuente con sus documentos, loader, OCR, splitter, embeddings, colección) y el
// botón que lanza la ingesta, con el progreso que el backend transmite por SSE.
// Los PDFs se eligen ARRIBA, en la etapa 01 (SourceInput.jsx): subidos desde el
// navegador (POST /ingest) o un bucket de GCS (POST /ingest/gcs).
import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  CircleSlash,
  Loader2,
  Play,
  RotateCcw,
  XCircle,
} from 'lucide-react'
import { ingestDocuments, ingestFromGcs } from '../api'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { formatSize } from './SourceInput'

const STEP_ICONS = {
  running: <Loader2 className="size-3.5 animate-spin text-primary" />,
  done: <CheckCircle2 className="size-3.5 text-emerald-400" />,
  skipped: <CircleSlash className="size-3.5 text-muted-foreground" />,
  error: <XCircle className="size-3.5 text-destructive" />,
}

const ROUTE_LABEL = {
  brute_force: 'fuerza bruta',
  mixed: 'mixta (parte en HNSW)',
  hnsw: 'HNSW',
}

// Ruta de indexación REAL que reporta Qdrant (no la deduce el frontend): cuántos
// vectores ya están en HNSW y si el optimizador sigue construyendo el índice.
function routeText(e) {
  const route = ROUTE_LABEL[e.index_route] || e.index_route
  const optimizing = e.optimizing ? ' · Qdrant sigue indexando' : ''
  return `${route} · ${(e.indexed_vectors ?? 0).toLocaleString()} de ${(e.num_vectors ?? 0).toLocaleString()} en HNSW${optimizing}`
}

// Detalle corto de un paso terminado, según los extras de cada evento.
function stepDetail(e) {
  if (e.status !== 'done') return null
  if (e.step === 'validate') return `${e.text_pages} con texto · ${e.ocr_pages} para OCR`
  if (e.step === 'load') return `${e.pages} páginas`
  if (e.step === 'ocr') return `${e.ocr_pages} páginas`
  if (e.step === 'boilerplate') return `${e.removed} líneas quitadas`
  if (e.step === 'chunk') return `${e.chunks} chunks`
  if (e.step === 'embed') return `${e.vectors} vectores · ${e.dim} dims`
  if (e.step === 'index') return routeText(e)
  return null
}

// Agrupa los eventos en { source, start, docs: {i: {filename, steps: {step: evt}, error}}, done, error }.
function reduceEvents(events) {
  const out = { source: null, start: null, docs: {}, done: null, error: null }
  for (const e of events) {
    if (e.event === 'source') out.source = e
    else if (e.event === 'start') out.start = e
    else if (e.event === 'done') out.done = e
    else if (e.event === 'error') out.error = e.error
    else if (e.event === 'step' || e.event === 'doc_error') {
      const d = (out.docs[e.doc] ||= {
        filename: e.filename,
        steps: {},
        error: null,
      })
      if (e.event === 'step') d.steps[e.step] = e
      else d.error = e.error
    }
  }
  return out
}

// Una fila del resumen: número de etapa, etapa, qué se usa y si es elección tuya.
function SummaryRow({ row, detail, warn }) {
  return (
    <li
      className={cn(
        'flex flex-wrap items-center gap-x-3 gap-y-0.5 rounded-md border px-3 py-1.5 sm:grid sm:grid-cols-[1.75rem_minmax(0,12rem)_minmax(0,1fr)_auto]',
        row.chosen ? 'border-primary/40 bg-primary/5' : 'border-transparent bg-muted/20',
      )}
    >
      <span className="font-mono text-[11px] text-muted-foreground">
        {row.number != null ? String(row.number).padStart(2, '0') : ''}
      </span>
      <span
        className={cn(
          'text-[12px] [overflow-wrap:anywhere]',
          row.chosen ? 'text-foreground' : 'text-muted-foreground',
        )}
      >
        {row.title}
      </span>
      <span className="flex min-w-0 flex-col">
        <span
          className={cn(
            'text-[13px] [overflow-wrap:anywhere]',
            row.chosen ? 'font-medium text-foreground' : 'text-muted-foreground',
          )}
        >
          {row.value || '—'}
        </span>
        {detail && (
          <span className={cn('text-[11px]', warn ? 'text-amber-400' : 'text-muted-foreground')}>
            {detail}
          </span>
        )}
      </span>
      <span
        className={cn(
          'ml-auto inline-flex h-5 shrink-0 items-center rounded-full border px-2 text-[11px] font-medium',
          row.chosen
            ? 'border-primary/50 bg-primary/15 text-primary'
            : row.auto
              ? 'border-sky-500/30 bg-sky-500/10 text-sky-400'
              : 'border-border text-muted-foreground',
        )}
      >
        {row.chosen ? 'Tu elección' : row.auto ? 'Automático' : 'Fijo'}
      </span>
    </li>
  )
}

// Qué documentos se van a ingestar, en una línea, según la fuente.
function docsSummary(fromGcs, docs) {
  if (fromGcs) {
    const bucket = docs.bucket.trim()
    return bucket ? `gs://${bucket}/${docs.prefix.trim()}` : null
  }
  if (!docs.files.length) return null
  const total = docs.files.reduce((acc, f) => acc + f.size, 0)
  return `${docs.files.length} PDF${docs.files.length === 1 ? '' : 's'} · ${formatSize(total)}`
}

export default function IngestPanel({
  rows,
  selection,
  docs,
  tenant,
  collection,
  isDefault,
  onReset,
}) {
  const [events, setEvents] = useState([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const fromGcs = selection.source === 'gcs'

  async function run() {
    setEvents([])
    setError(null)
    setRunning(true)
    const common = {
      tenant: tenant.trim(),
      loader: selection.loader,
      ocrEngine: selection.ocr_engine,
      splitter: selection.splitter,
      embedder: selection.embedder,
      onEvent: (e) => setEvents((prev) => [...prev, e]),
    }
    try {
      if (fromGcs)
        await ingestFromGcs({
          ...common,
          bucket: docs.bucket.trim(),
          prefix: docs.prefix.trim(),
        })
      else await ingestDocuments({ ...common, files: docs.files })
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const log = reduceEvents(events)
  const summary = docsSummary(fromGcs, docs)
  // La colección se elige en la etapa 09 (CollectionInput): válida y sin choque de dimensión.
  const collectionOk = Boolean(collection?.valid) && !collection?.dimension_error
  const canRun = !running && collectionOk && Boolean(summary)

  return (
    <div className="w-full max-w-4xl rounded-xl border border-primary/40 bg-card p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary">
          <Play className="size-4.5" />
        </span>
        <div>
          <h3 className="text-[15px] font-semibold">Ejecutar ingesta</h3>
          <p className="text-[13px] text-muted-foreground">
            Tu pipeline completo, de la 01 a la 09. Lo resaltado lo eligiste tú en el diagrama.
          </p>
        </div>
      </div>

      <ul className="mt-4 flex flex-col gap-1">
        {rows.map((row) => {
          // Detalles en vivo de las etapas que dependen de lo que escribiste o subiste.
          if (row.key === 'source') {
            return (
              <SummaryRow
                key={row.key}
                row={row}
                detail={
                  summary ||
                  (fromGcs ? 'Falta el bucket (etapa 01)' : 'Sin PDFs: súbelos en la etapa 01')
                }
                warn={!summary}
              />
            )
          }
          if (row.key === 'store') {
            return (
              <SummaryRow
                key={row.key}
                row={{ ...row, value: collection?.valid ? collection.collection : null }}
                detail={
                  !collection?.valid
                    ? 'Falta el nombre: escríbelo en la etapa 09'
                    : collection.dimension_error
                      ? 'Choque de dimensión: mira la etapa 09'
                      : collection.exists
                        ? 'Existente: los PDFs se añaden'
                        : 'Nueva: se crea al ingestar'
                }
                warn={!collectionOk}
              />
            )
          }
          return <SummaryRow key={row.key} row={row} />
        })}
      </ul>

      <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
        <span className="mr-auto flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <CheckCircle2 className="size-3.5 text-emerald-400" />
          Tu configuración se guarda sola en este navegador (los PDFs no).
        </span>
        <Button variant="ghost" size="sm" onClick={onReset} disabled={isDefault}>
          <RotateCcw className="size-3.5" /> Restablecer opciones
        </Button>
      </div>

      <div className="mt-4 flex justify-end">
        <Button onClick={run} disabled={!canRun}>
          {running ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Ingestando…
            </>
          ) : (
            <>
              <Play className="size-4" /> Ejecutar ingesta
            </>
          )}
        </Button>
      </div>

      {(error || log.error) && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>{error || log.error}</span>
        </div>
      )}

      {log.source && !log.start && (
        <p className="mt-4 flex items-center gap-2 text-[12px] text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin text-primary" />
          Descargando {log.source.num_files} PDF
          {log.source.num_files === 1 ? '' : 's'} de gs://
          {log.source.bucket}…
        </p>
      )}

      {log.start && (
        <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
          <p className="text-[12px] text-muted-foreground">
            Colección <span className="font-mono text-foreground">{log.start.collection}</span> ·{' '}
            {log.start.model} ({log.start.dimension} dims) · loader{' '}
            <span className="font-mono text-foreground">{log.start.loader}</span> · splitter{' '}
            <span className="font-mono text-foreground">{log.start.splitter}</span>
          </p>
          {Object.entries(log.docs).map(([i, d]) => (
            <div key={i} className="rounded-md border border-border px-3 py-2">
              <p className="text-[13px] font-medium">{d.filename}</p>
              <ul className="mt-1.5 flex flex-col gap-1">
                {Object.values(d.steps).map((s) => (
                  <li key={s.step} className="flex items-center gap-2 text-[12px]">
                    {STEP_ICONS[s.status] || <Circle className="size-3.5" />}
                    <span className={cn(s.status === 'skipped' && 'text-muted-foreground')}>
                      {s.label}
                    </span>
                    {stepDetail(s) && (
                      <span className="font-mono text-[11px] text-muted-foreground">
                        · {stepDetail(s)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {d.error && <p className="mt-1.5 text-[12px] text-destructive">{d.error}</p>}
            </div>
          ))}
          {log.done && (
            <>
              <p className="flex items-center gap-2 text-[13px] text-emerald-400">
                <CheckCircle2 className="size-4" />
                Listo: {log.done.num_vectors.toLocaleString()} vectores en {log.done.collection}
              </p>
              {log.done.vectors_threshold > 0 && (
                <p className="text-[12px] text-muted-foreground">
                  Ruta de búsqueda: {routeText(log.done)}. Qdrant pasa un segmento a HNSW cuando
                  supera {log.done.indexing_threshold.toLocaleString()} KB de vectores (≈{' '}
                  {log.done.vectors_threshold.toLocaleString()} vectores de esta colección).
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
