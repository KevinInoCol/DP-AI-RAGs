// Etapa 09 · nombre de la colección de Qdrant. El prefijo `tenant_id_` es FIJO (se
// ve pero no se edita); el usuario escribe solo el resto. El nombre final lo
// calcula el backend con las mismas reglas que la ingesta (pipeline/naming.py), así
// lo que se ve es exactamente lo que se crea. Debajo, las colecciones que ya existen
// para reutilizarlas con un click.
import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Database, Info, Loader2 } from 'lucide-react'
import { fetchCollections, previewCollection } from '../api'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

const PREFIX = 'tenant_id_'

export default function CollectionInput({ tenant, onTenantChange, embedder, onPreview }) {
  const [preview, setPreview] = useState(null)
  const [checking, setChecking] = useState(false)
  const [existing, setExisting] = useState(null)
  // Cada consulta lleva un número: si llega una respuesta vieja (la de un nombre o
  // embedder anterior), se descarta. Qdrant está en un VPS y tarda ~1 s.
  const requestId = useRef(0)

  useEffect(() => {
    fetchCollections()
      .then(setExisting)
      .catch(() => setExisting({ collections: [], error: 'No se pudo leer Qdrant' }))
  }, [])

  // Vista previa con un pequeño retardo para no llamar al backend en cada tecla.
  useEffect(() => {
    const id = ++requestId.current
    // Mientras se comprueba, el resultado anterior ya no vale (ni para el panel).
    setPreview(null)
    onPreview(null)
    if (!tenant.trim()) {
      setChecking(false)
      return
    }
    setChecking(true)
    const timer = setTimeout(() => {
      previewCollection({ tenant, embedder })
        .then((p) => {
          if (id !== requestId.current) return
          setPreview(p)
          onPreview(p)
        })
        .catch(() => {})
        .finally(() => {
          if (id === requestId.current) setChecking(false)
        })
    }, 300)
    return () => clearTimeout(timer)
    // onPreview es estable (setState del padre)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenant, embedder])

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="collection-name" className="text-xs text-muted-foreground">
        Nombre de la colección
      </Label>
      <div className="flex h-9 items-stretch overflow-hidden rounded-lg border border-input focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
        <span className="flex items-center border-r border-input bg-muted/50 px-3 font-mono text-[13px] text-muted-foreground select-none">
          {PREFIX}
        </span>
        <input
          id="collection-name"
          value={tenant}
          onChange={(e) => onTenantChange(e.target.value)}
          placeholder="municipio_girardota"
          className="min-w-0 flex-1 bg-transparent px-3 font-mono text-[13px] outline-none placeholder:text-muted-foreground"
        />
      </div>

      {/* Estado del nombre: final, nueva/existente, errores */}
      {tenant.trim() && (
        <div className="text-[12px]">
          {checking ? (
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Comprobando…
            </span>
          ) : preview && !preview.valid ? (
            <span className="flex items-start gap-1.5 text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              Usa al menos 2 letras o números.
            </span>
          ) : preview ? (
            <div className="flex flex-col gap-1">
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground">Se usará</span>
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
                  {preview.collection}
                </code>
                {preview.exists === true && (
                  <span className="text-sky-400">
                    · ya existe ({preview.num_vectors.toLocaleString()} vectores): los PDFs se
                    añaden
                  </span>
                )}
                {preview.exists === false && (
                  <span className="text-emerald-400">· nueva: se crea al ingestar</span>
                )}
              </span>
              {preview.dimension_error ? (
                <span className="flex items-start gap-1.5 text-destructive">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                  {preview.dimension_error}
                </span>
              ) : (
                preview.exists && (
                  <span className="flex items-start gap-1.5 text-muted-foreground">
                    <Info className="mt-0.5 size-3.5 shrink-0" />
                    Asegúrate de que se creó con el mismo modelo de embeddings: con la misma
                    dimensión, Qdrant no puede distinguir dos modelos distintos.
                  </span>
                )
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Colecciones existentes, para reutilizar con un click */}
      {existing?.collections?.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[12px] text-muted-foreground">Existentes:</span>
          {existing.collections.map((c) => {
            const active = preview?.collection === c.collection
            return (
              <button
                key={c.collection}
                type="button"
                onClick={() => onTenantChange(c.tenant)}
                className={cn(
                  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-mono text-[11px] transition-colors',
                  active
                    ? 'border-primary/60 bg-primary/15 text-primary'
                    : 'border-border text-muted-foreground hover:border-primary/40 hover:text-foreground',
                )}
                title={`${c.num_vectors.toLocaleString()} vectores · ${c.dimension ?? '?'} dims`}
              >
                {active ? <CheckCircle2 className="size-3" /> : <Database className="size-3" />}
                {c.tenant}
              </button>
            )
          })}
        </div>
      )}
      {existing?.error && (
        <p className="text-[11px] text-muted-foreground">
          No se pudieron listar las colecciones existentes ({existing.error}).
        </p>
      )}
    </div>
  )
}
