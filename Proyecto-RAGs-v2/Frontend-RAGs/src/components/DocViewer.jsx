// Muestra los Document(s) extraídos por un loader + estadísticas y metadata.
import { FileSearch } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import StatGrid from './StatGrid'

function EmptyState({ children }) {
  return (
    <Card className="items-center gap-2 border-dashed py-12 text-center">
      <FileSearch className="size-6 text-muted-foreground/60" />
      <p className="text-sm text-muted-foreground">{children}</p>
    </Card>
  )
}

export default function DocViewer({ result, loading }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    )
  }
  if (!result) {
    return <EmptyState>El texto extraído aparecerá aquí después de procesar el archivo.</EmptyState>
  }
  if (result.num_documents === 0) {
    return <EmptyState>No se extrajo texto (¿PDF escaneado o vacío?).</EmptyState>
  }

  const { stats, documents } = result

  return (
    <div className="flex flex-col gap-5">
      <StatGrid
        stats={[
          { label: 'Documentos', value: stats.total_documents },
          { label: 'Caracteres totales', value: stats.total_chars.toLocaleString() },
          { label: 'Caracteres/doc (prom.)', value: stats.avg_chars },
        ]}
      />

      <div className="flex flex-col gap-3">
        {documents.map((d, i) => (
          <Card
            key={i}
            className="gap-3 overflow-hidden border-l-4 p-4"
            style={{ borderLeftColor: 'var(--chart-2)' }}
          >
            <div className="flex items-center gap-3">
              <span
                className="rounded-md px-2 py-0.5 font-mono text-xs font-semibold text-white"
                style={{ backgroundColor: 'var(--chart-2)' }}
              >
                Doc #{i + 1}
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                {d.text.length.toLocaleString()} caracteres
              </span>
            </div>

            {Object.keys(d.metadata || {}).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(d.metadata).map(([k, v]) => (
                  <Badge key={k} variant="secondary" className="font-mono text-[11px] font-normal">
                    <span className="text-muted-foreground">{k}:</span>&nbsp;{String(v)}
                  </Badge>
                ))}
              </div>
            )}

            <pre className="whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-3 font-mono text-[13px] leading-relaxed">
              {d.text || '(sin texto)'}
            </pre>
          </Card>
        ))}
      </div>
    </div>
  )
}
