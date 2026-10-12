// Menú lateral con AMBAS secciones desplegadas a la vez:
//   Document Loaders   (ordenados de peor a mejor, con indicador de calidad)
//   Text Splitters     (en dos subgrupos: LlamaIndex y LangChain)
// La selección de cada sección queda siempre resaltada; el punto "viendo"
// marca qué panel se muestra en el área principal.
import { FileText, Scissors, KeyRound, Boxes, Layers, Database, Workflow } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

function QualityMeter({ quality, max = 6 }) {
  const q = Math.max(0, Math.min(quality ?? 0, max))
  return (
    <span className="flex items-end gap-[2px]" title={`Calidad ${q}/${max}`}>
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          className={cn(
            'w-[3px] rounded-full transition-colors',
            i < q ? 'bg-primary' : 'bg-muted-foreground/25',
          )}
          style={{ height: `${5 + i * 2}px` }}
        />
      ))}
    </span>
  )
}

function MenuItem({ item, selected, onSelect, showQuality, maxQuality = 6 }) {
  // `available` solo lo traen los embedders: false = su API key NO está en el .env.
  const unavailable = item.available === false

  return (
    <button
      onClick={() => onSelect(item.key)}
      className={cn(
        'group relative flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-[13px] transition-colors',
        selected
          ? 'bg-sidebar-accent text-sidebar-accent-foreground'
          : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
        unavailable && 'opacity-45',
      )}
    >
      {selected && (
        <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-primary" />
      )}
      <span className="truncate font-medium">{item.name}</span>
      <span className="flex shrink-0 items-center gap-2">
        {/* "auto" = el que el backend elige solo cuando no se le especifica ninguno */}
        {item.is_default && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="rounded bg-primary/15 px-1.5 py-px font-mono text-[10px] font-medium text-primary">
                auto
              </span>
            </TooltipTrigger>
            <TooltipContent>
              El que se usa por defecto (su API key está disponible)
            </TooltipContent>
          </Tooltip>
        )}
        {showQuality && item.quality != null && (
          <QualityMeter quality={item.quality} max={maxQuality} />
        )}
        {item.requires_api_key && (
          <Tooltip>
            <TooltipTrigger asChild>
              <KeyRound
                className={cn(
                  'size-3.5',
                  unavailable ? 'text-destructive/70' : 'text-amber-400/80',
                )}
              />
            </TooltipTrigger>
            <TooltipContent>
              {unavailable
                ? `Falta ${item.requires_env} en el .env`
                : item.requires_env
                  ? `Usa ${item.requires_env}`
                  : 'Requiere API Key'}
            </TooltipContent>
          </Tooltip>
        )}
      </span>
    </button>
  )
}

// Agrupa los items por `groupBy` respetando el orden en que llegan del backend.
function groupItems(items, groupBy) {
  const groups = []
  for (const it of items) {
    const key = it[groupBy]
    let group = groups.find((g) => g.key === key)
    if (!group) {
      group = { key, label: it[`${groupBy}_name`] ?? key, items: [] }
      groups.push(group)
    }
    group.items.push(it)
  }
  return groups
}

function Section({ title, icon: Icon, items, selectedKey, onSelect, active, showQuality, maxQuality, groupBy }) {
  const renderItems = (list) =>
    list.map((it) => (
      <MenuItem
        key={it.key}
        item={it}
        selected={it.key === selectedKey}
        onSelect={onSelect}
        showQuality={showQuality}
        maxQuality={maxQuality}
      />
    ))

  return (
    <div className={cn('rounded-lg p-1.5 transition-colors', active && 'bg-primary/5')}>
      <div className="mb-1 flex items-center justify-between px-2 py-1">
        <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          <Icon className="size-3.5" />
          {title}
        </span>
        {active && (
          <span className="flex items-center gap-1 text-[10px] font-medium text-primary">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            viendo
          </span>
        )}
      </div>
      <div className="flex flex-col gap-0.5">
        {items.length === 0 ? (
          <div className="px-3 py-2 text-[13px] text-muted-foreground">Cargando…</div>
        ) : groupBy ? (
          groupItems(items, groupBy).map((g) => (
            <div key={g.key} className="mt-2 flex flex-col gap-0.5 first:mt-0">
              <div className="flex items-center gap-2 px-3 pb-0.5 pt-1">
                <span className="text-[11px] font-semibold text-sidebar-foreground/80">{g.label}</span>
                <span className="h-px flex-1 bg-sidebar-border" />
                <span className="font-mono text-[10px] text-muted-foreground">{g.items.length}</span>
              </div>
              {renderItems(g.items)}
            </div>
          ))
        ) : (
          renderItems(items)
        )}
      </div>
    </div>
  )
}

export default function Sidebar({
  loaders,
  splitters,
  embedders,
  vectorstores,
  maxQuality,
  selLoader,
  selSplitter,
  selEmbedder,
  selStore,
  activeTab,
  onSelectLoader,
  onSelectSplitter,
  onSelectEmbedder,
  onSelectStore,
  onSelectPipeline,
}) {
  return (
    <aside className="sticky top-0 flex h-screen w-72 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
          <Boxes className="size-5" />
        </span>
        <div className="leading-tight">
          <div className="text-sm font-semibold">RAG Toolkit</div>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1 px-3">
        <div className="flex flex-col gap-2 pb-4">
          <button
            onClick={onSelectPipeline}
            className={cn(
              'relative flex items-center gap-2 rounded-lg px-3.5 py-2.5 text-left text-[13px] font-medium transition-colors',
              activeTab === 'pipeline'
                ? 'bg-primary/10 text-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
            )}
          >
            {activeTab === 'pipeline' && (
              <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-primary" />
            )}
            <Workflow className="size-4 text-primary" />
            Pipeline de ingesta
          </button>
          <Section
            title="Document Loaders"
            icon={FileText}
            items={loaders}
            selectedKey={selLoader}
            onSelect={onSelectLoader}
            active={activeTab === 'loaders'}
            showQuality
            maxQuality={maxQuality}
          />
          <Section
            title="Text Splitters"
            icon={Scissors}
            items={splitters}
            selectedKey={selSplitter}
            onSelect={onSelectSplitter}
            active={activeTab === 'splitters'}
            groupBy="framework"
          />
          <Section
            title="Embeddings"
            icon={Layers}
            items={embedders}
            selectedKey={selEmbedder}
            onSelect={onSelectEmbedder}
            active={activeTab === 'embedders'}
          />
          <Section
            title="Vector Stores"
            icon={Database}
            items={vectorstores}
            selectedKey={selStore}
            onSelect={onSelectStore}
            active={activeTab === 'vectorstores'}
          />
        </div>
      </ScrollArea>

      <div className="border-t border-sidebar-border px-5 py-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <KeyRound className="size-3 text-amber-400/80" /> API Key
        </span>
        <span className="mx-1.5">·</span>
        <span className="inline-flex items-center gap-1">
          <KeyRound className="size-3 text-destructive/70" /> key faltante
        </span>
        <span className="mx-1.5">·</span>
        barras = calidad del loader
      </div>
    </aside>
  )
}
