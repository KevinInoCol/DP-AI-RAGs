// Etapa 01 · de dónde salen los PDFs. Se muestra DENTRO de la tarjeta "Carga de
// documentos", debajo de sus opciones, y cambia según la fuente elegida:
//   upload → zona para arrastrar y soltar PDFs (o hacer click para elegirlos)
//   gcs    → bucket + prefijo, con "Ver PDFs" para revisar antes de ingestar
// El estado (archivos, bucket, prefijo) vive en PipelineView: lo usa también el
// panel "Ejecutar ingesta" del final.
import { useRef, useState } from 'react'
import { AlertTriangle, Cloud, FileText, Loader2, Upload, X } from 'lucide-react'
import { listGcsPdfs } from '../api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export function formatSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

const isPdf = (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')

function Dropzone({ files, onChange }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [rejected, setRejected] = useState([])

  // Suma los nuevos a los ya elegidos (sin duplicar por nombre + tamaño) y
  // descarta lo que no sea PDF, avisando cuáles.
  function addFiles(list) {
    const incoming = Array.from(list || [])
    const pdfs = incoming.filter(isPdf)
    setRejected(incoming.filter((f) => !isPdf(f)).map((f) => f.name))
    const seen = new Set(files.map((f) => `${f.name}:${f.size}`))
    onChange([...files, ...pdfs.filter((f) => !seen.has(`${f.name}:${f.size}`))])
  }

  const total = files.reduce((acc, f) => acc + f.size, 0)

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          addFiles(e.dataTransfer.files)
        }}
        className={cn(
          'flex flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
          dragging
            ? 'border-primary bg-primary/10'
            : 'border-border hover:border-primary/50 hover:bg-muted/30',
        )}
      >
        <Upload className={cn('size-5', dragging ? 'text-primary' : 'text-muted-foreground')} />
        <span className="text-[13px] font-medium">
          {dragging ? 'Suelta los PDFs aquí' : 'Arrastra tus PDFs aquí o haz click para elegirlos'}
        </span>
        <span className="text-[12px] text-muted-foreground">Puedes subir varios a la vez · solo .pdf</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          addFiles(e.target.files)
          e.target.value = ''
        }}
      />

      {rejected.length > 0 && (
        <p className="flex items-center gap-1.5 text-[12px] text-amber-400">
          <AlertTriangle className="size-3.5 shrink-0" />
          No son PDF y se ignoraron: {rejected.join(', ')}
        </p>
      )}

      {files.length > 0 && (
        <div className="rounded-md border border-border">
          <div className="flex items-center justify-between border-b border-border px-3 py-1.5 text-[12px] text-muted-foreground">
            <span>
              {files.length} PDF{files.length === 1 ? '' : 's'} · {formatSize(total)}
            </span>
            <button
              type="button"
              onClick={() => onChange([])}
              className="rounded px-1 hover:text-foreground"
            >
              Quitar todos
            </button>
          </div>
          <ul className="max-h-48 overflow-y-auto">
            {files.map((f, i) => (
              <li
                key={`${f.name}:${f.size}`}
                className="flex items-center gap-2 px-3 py-1.5 text-[12px] odd:bg-muted/20"
              >
                <FileText className="size-3.5 shrink-0 text-primary" />
                <span className="min-w-0 flex-1 truncate font-mono">{f.name}</span>
                <span className="shrink-0 text-muted-foreground">{formatSize(f.size)}</span>
                <button
                  type="button"
                  onClick={() => onChange(files.filter((_, j) => j !== i))}
                  aria-label={`Quitar ${f.name}`}
                  className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function BucketFields({ bucket, prefix, onChange }) {
  const [pdfs, setPdfs] = useState(null)
  const [listing, setListing] = useState(false)
  const [error, setError] = useState(null)

  async function listBucket() {
    setError(null)
    setPdfs(null)
    setListing(true)
    try {
      const data = await listGcsPdfs({ bucket: bucket.trim(), prefix: prefix.trim() })
      setPdfs(data.pdfs)
    } catch (e) {
      setError(e.message)
    } finally {
      setListing(false)
    }
  }

  function update(field, value) {
    setPdfs(null)
    setError(null)
    onChange({ bucket, prefix, [field]: value })
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="source-bucket" className="text-xs text-muted-foreground">
            Bucket de GCS (sin gs://)
          </Label>
          <Input
            id="source-bucket"
            value={bucket}
            onChange={(e) => update('bucket', e.target.value)}
            placeholder="p. ej. mi-bucket-documentos"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="source-prefix" className="text-xs text-muted-foreground">
            Prefijo / carpeta (opcional)
          </Label>
          <div className="flex gap-2">
            <Input
              id="source-prefix"
              value={prefix}
              onChange={(e) => update('prefix', e.target.value)}
              placeholder="p. ej. manuales/2024/"
            />
            <Button variant="outline" onClick={listBucket} disabled={listing || !bucket.trim()}>
              {listing ? <Loader2 className="size-4 animate-spin" /> : <Cloud className="size-4" />}
              Ver PDFs
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <p className="flex items-start gap-1.5 text-[12px] text-destructive">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          {error}
        </p>
      )}
      {pdfs && (
        <div className="max-h-48 overflow-y-auto rounded-md border border-border px-3 py-2">
          {pdfs.length ? (
            <>
              <p className="mb-1 text-[12px] text-muted-foreground">
                Se ingestarán {pdfs.length} PDF{pdfs.length === 1 ? '' : 's'}:
              </p>
              <ul className="flex flex-col gap-0.5 font-mono text-[11px] text-muted-foreground">
                {pdfs.map((f) => (
                  <li key={f.name} className="flex justify-between gap-3">
                    <span className="truncate">{f.name}</span>
                    <span className="shrink-0">{formatSize(f.size)}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-[12px] text-muted-foreground">No hay PDFs en ese bucket/prefijo.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function SourceInput({ source, docs, onChange }) {
  if (source === 'gcs') {
    return (
      <BucketFields
        bucket={docs.bucket}
        prefix={docs.prefix}
        onChange={(v) => onChange({ ...docs, ...v })}
      />
    )
  }
  return <Dropzone files={docs.files} onChange={(files) => onChange({ ...docs, files })} />
}
