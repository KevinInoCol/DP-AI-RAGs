import { useRef } from 'react'
import { Upload, Trash2, Scissors, Loader2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

// Entrada del documento: pegar texto en un textarea O subir un archivo.
export default function DocumentInput({ text, onChangeText, onFile, onRun, loading }) {
  const fileRef = useRef(null)

  const chars = text.length
  const words = text.trim() ? text.trim().split(/\s+/).length : 0

  return (
    <Card className="gap-0 p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <h2 className="text-sm font-semibold">Documento</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
            <Upload className="size-3.5" /> Subir archivo
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.md,.pdf,.py,.js,.ts,.java,.go,.cpp,.html,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) onFile(f)
              e.target.value = ''
            }}
          />
          <Button variant="ghost" size="sm" onClick={() => onChangeText('')}>
            <Trash2 className="size-3.5" /> Limpiar
          </Button>
        </div>
      </div>

      <div className="p-5">
        <Textarea
          value={text}
          onChange={(e) => onChangeText(e.target.value)}
          placeholder="Pega aquí tu texto o sube un archivo (.txt, .md, .pdf, código…)"
          rows={10}
          className="resize-y font-mono text-[13px] leading-relaxed"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3">
        <span className="font-mono text-xs text-muted-foreground">
          {chars.toLocaleString()} caracteres · {words.toLocaleString()} palabras
        </span>
        <Button onClick={onRun} disabled={loading || !text.trim()}>
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Dividiendo…
            </>
          ) : (
            <>
              <Scissors className="size-4" /> Dividir texto
            </>
          )}
        </Button>
      </div>
    </Card>
  )
}
