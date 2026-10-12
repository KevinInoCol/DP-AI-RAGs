// Controles dinámicos de parámetros según el splitter seleccionado.
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export default function ParamControls({ params, values, onChange }) {
  if (!params || params.length === 0) return null

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4">
      {params.map((p) => (
        <div key={p.name} className="flex flex-col gap-1.5">
          <Label className="text-xs font-medium text-muted-foreground">{p.label}</Label>
          {p.type === 'select' ? (
            <Select
              value={String(values[p.name] ?? p.default)}
              onValueChange={(v) => onChange(p.name, v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {p.options.map((opt) => (
                  <SelectItem key={opt} value={String(opt)}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              type="number"
              className="font-mono"
              value={values[p.name] ?? p.default}
              min={p.min}
              max={p.max}
              step={p.step}
              onChange={(e) =>
                onChange(
                  p.name,
                  p.type === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10),
                )
              }
            />
          )}
        </div>
      ))}
    </div>
  )
}
