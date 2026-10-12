// Muestra los chunks resultantes como tarjetas + estadísticas globales.
import { Inbox } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import StatGrid from './StatGrid'
import { chunkColor } from '@/lib/palette'

function EmptyState({ icon: Icon = Inbox, children }) {
  return (
    <Card className="items-center gap-2 border-dashed py-12 text-center">
      <Icon className="size-6 text-muted-foreground/60" />
      <p className="text-sm text-muted-foreground">{children}</p>
    </Card>
  )
}

export default function ChunkViewer({ result, loading }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    )
  }
  if (!result) {
    return <EmptyState>Los chunks aparecerán aquí después de dividir el texto.</EmptyState>
  }
  if (result.num_chunks === 0) {
    return <EmptyState>No se generaron chunks (¿texto vacío?).</EmptyState>
  }

  const { stats, chunks } = result
  const maxTokens = Math.max(...chunks.map((c) => c.token_count || 0), 1)

  return (
    <div className="flex flex-col gap-5">
      <StatGrid
        stats={[
          { label: 'Chunks', value: stats.total_chunks },
          { label: 'Tokens totales', value: stats.total_tokens.toLocaleString() },
          { label: 'Tokens/chunk (prom.)', value: stats.avg_tokens },
          { label: 'Caracteres/chunk (prom.)', value: stats.avg_chars },
        ]}
      />

      <div className="flex flex-col gap-3">
        {chunks.map((c) => {
          const color = chunkColor(c.index)
          return (
            <Card
              key={c.index}
              className="gap-3 overflow-hidden border-l-4 p-4"
              style={{ borderLeftColor: color }}
            >
              <div className="flex items-center gap-3">
                <span
                  className="rounded-md px-2 py-0.5 font-mono text-xs font-semibold text-white"
                  style={{ backgroundColor: color }}
                >
                  #{c.index + 1}
                </span>
                <span className="font-mono text-xs text-muted-foreground">
                  {c.token_count} tokens · {c.char_count} caracteres
                </span>
                <span className="ml-auto h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full"
                    style={{
                      width: `${((c.token_count || 0) / maxTokens) * 100}%`,
                      backgroundColor: color,
                    }}
                  />
                </span>
              </div>
              <pre className="whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-3 font-mono text-[13px] leading-relaxed">
                {c.text}
              </pre>
              {c.metadata && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(c.metadata).map(([k, v]) => (
                    <span
                      key={k}
                      className="rounded-md bg-muted px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
                    >
                      <b className="font-semibold text-foreground">{k}</b> {String(v)}
                    </span>
                  ))}
                </div>
              )}
              {c.window && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-primary hover:underline">
                    Ver ventana de contexto
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-3 font-mono text-[13px] leading-relaxed">
                    {c.window}
                  </pre>
                </details>
              )}
            </Card>
          )
        })}
      </div>
    </div>
  )
}
