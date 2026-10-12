// Fila de métricas destacadas (números en mono, estilo panel de datos).
import { Card } from '@/components/ui/card'

export default function StatGrid({ stats }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
      {stats.map((s) => (
        <Card key={s.label} className="gap-1 p-4">
          <div className="font-mono text-2xl font-semibold tracking-tight tabular-nums">
            {s.value}
          </div>
          <div className="text-xs text-muted-foreground">{s.label}</div>
        </Card>
      ))}
    </div>
  )
}
