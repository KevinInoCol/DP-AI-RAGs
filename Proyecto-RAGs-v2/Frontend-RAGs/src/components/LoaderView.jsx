import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Building2, CircleDollarSign, Cpu, FileType, Paperclip, Download, Loader2 } from 'lucide-react'
import { loadDocument } from '../api'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import DocViewer from './DocViewer'

function QualityMeter({ quality, max = 6 }) {
  const q = Math.max(0, Math.min(quality ?? 0, max))
  return (
    <span className="flex items-center gap-1" title={`Calidad ${q}/${max}`}>
      <span className="flex items-end gap-[2px]">
        {Array.from({ length: max }).map((_, i) => (
          <span
            key={i}
            className={cn('w-1 rounded-full', i < q ? 'bg-primary' : 'bg-muted-foreground/25')}
            style={{ height: `${6 + i * 3}px` }}
          />
        ))}
      </span>
      <span className="font-mono text-xs text-muted-foreground">
        {q}/{max}
      </span>
    </span>
  )
}

// Pestaña de Document Loaders (extracción): archivo -> Document(s).
export default function LoaderView({ selected, maxQuality = 6 }) {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  // Al cambiar de loader, limpiar el resultado anterior.
  useEffect(() => {
    setResult(null)
    setError(null)
  }, [selected])

  async function handleLoad() {
    if (!selected || !file) return
    setLoading(true)
    setError(null)
    try {
      const data = await loadDocument({ loader: selected.key, file })
      setResult(data)
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  if (!selected) return null

  return (
    <div className="flex flex-col gap-5">
      <Card className="gap-4 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">{selected.name}</h2>
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
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-muted-foreground">
          <QualityMeter quality={selected.quality} max={maxQuality} />
          {selected.provider && (
            <span className="flex items-center gap-1.5">
              <Building2 className="size-3.5" /> Proveedor:{' '}
              <span className="font-medium text-foreground/90">{selected.provider}</span>
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <Cpu className="size-3.5" /> Motor: <span className="font-mono">{selected.engine}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <FileType className="size-3.5" />
            <span className="font-mono">{selected.accepts.join(' · ')}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <CircleDollarSign className="size-3.5" />
            <span className="font-mono">
              {selected.cost_usd_per_1k_pages
                ? `$${selected.cost_usd_per_1k_pages.toFixed(2)} / 1,000 pág.`
                : 'Gratis (local)'}
            </span>
          </span>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{selected.description}</p>
      </Card>

      <Card className="gap-0 p-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">Archivo</h2>
          <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
            <Paperclip className="size-3.5" /> Elegir archivo
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept={selected.accepts.join(',')}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) {
                setFile(f)
                setResult(null)
              }
              e.target.value = ''
            }}
          />
        </div>

        <div className="p-5">
          <div
            className={cn(
              'flex items-center justify-center rounded-lg border border-dashed px-5 py-8 text-center text-sm',
              file
                ? 'border-primary/50 bg-primary/5 text-foreground'
                : 'border-border bg-muted/30 text-muted-foreground',
            )}
          >
            {file ? (
              <span className="flex items-center gap-2">
                <Paperclip className="size-4 text-primary" />
                <b className="font-medium">{file.name}</b>
                <span className="font-mono text-xs text-muted-foreground">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
              </span>
            ) : (
              <span>
                Selecciona un archivo para extraer su texto ({selected.accepts.join(', ')})
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3">
          <span className="text-xs text-muted-foreground">
            {selected.requires_api_key
              ? 'Requiere LLAMA_CLOUD_API_KEY en el backend'
              : 'Extracción local, sin API key'}
          </span>
          <Button onClick={handleLoad} disabled={loading || !file}>
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Extrayendo…
              </>
            ) : (
              <>
                <Download className="size-4" /> Extraer texto
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

      <DocViewer result={result} loading={loading} />
    </div>
  )
}
