// Pestaña Pipeline: el flujo de ingesta de ARRIBA hacia ABAJO, con las opciones
// de cada etapa. El flujo viene del backend (GET /pipeline), que lo arma desde
// los catálogos reales, así el diagrama no se desincroniza del código.
//
//   paso ─▶ paso ─▶ ◆ decisión ─┬─ No ─ rama izquierda ─┬─▶ paso …
//                                └─ Sí ─ rama derecha  ──┘
import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Building2,
  ChevronDown,
  Database,
  Eraser,
  FileText,
  Fingerprint,
  KeyRound,
  Layers,
  Loader2,
  ScanText,
  Scissors,
  ShieldCheck,
  Type,
  UserRound,
} from 'lucide-react'
import { fetchPipeline } from '../api'
import { cn } from '@/lib/utils'

const NODE_ICONS = {
  upload: UserRound,
  load: FileText,
  validate: ShieldCheck,
  normalize: Type,
  boilerplate: Eraser,
  chunk: Scissors,
  metadata: Fingerprint,
  embed: Layers,
  store: Database,
}

// Qué significa cada estado de opción (ver pipeline/flow.py).
const STATUS = {
  active: {
    label: 'En uso',
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  },
  selectable: {
    label: 'Elegible en ingesta',
    className: 'border-sky-500/30 bg-sky-500/10 text-sky-400',
  },
  testbed: {
    label: 'Comparable en su pestaña',
    className: 'border-border bg-muted/40 text-muted-foreground',
  },
  planned: {
    label: 'Pendiente',
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  },
}

function StatusPill({ status }) {
  const s = STATUS[status] || STATUS.testbed
  return (
    <span
      className={cn(
        'inline-flex h-5 shrink-0 items-center rounded-full border px-2 text-[11px] font-medium',
        s.className,
      )}
    >
      {s.label}
    </span>
  )
}

// Precio de cada opción (pricing.kind viene del catálogo en el backend).
const PRICING = {
  free: { label: 'Gratis', className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' },
  paid: { label: 'De pago', className: 'border-amber-500/30 bg-amber-500/10 text-amber-400' },
  freemium: { label: 'Mixto', className: 'border-sky-500/30 bg-sky-500/10 text-sky-400' },
}

function PricePill({ pricing }) {
  if (!pricing) return null
  const p = PRICING[pricing.kind] || PRICING.paid
  return (
    <span
      className={cn(
        'inline-flex h-5 shrink-0 items-center gap-1 rounded-md border px-1.5 text-[11px]',
        p.className,
      )}
      title={pricing.note || undefined}
    >
      <span className="font-semibold">{p.label}</span>
      {pricing.kind !== 'free' && pricing.label && (
        <span className="font-mono">· {pricing.label}</span>
      )}
    </span>
  )
}

function ProviderLine({ provider }) {
  return (
    <span className="flex items-center gap-1 text-[12px] text-muted-foreground">
      <Building2 className="size-3.5 shrink-0" />
      <span>
        Proveedor: <span className="font-medium text-foreground/90">{provider}</span>
      </span>
    </span>
  )
}

function OptionRow({ option }) {
  return (
    <li
      className={cn(
        'flex flex-col gap-1 rounded-md border px-3 py-2',
        option.status === 'active' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-border',
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium">{option.name}</span>
        {option.requires_api_key && (
          <KeyRound className="size-3.5 text-amber-400/80" aria-label="Requiere API Key" />
        )}
        <span className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          <PricePill pricing={option.pricing} />
          <StatusPill status={option.status} />
        </span>
      </div>
      {option.provider && <ProviderLine provider={option.provider} />}
      {option.pricing?.note && (
        <p className="text-[11px] leading-relaxed text-muted-foreground/90">
          <span className="font-medium">Precio:</span> {option.pricing.note}
        </p>
      )}
      {option.description && (
        <p className="text-[12px] leading-relaxed text-muted-foreground">{option.description}</p>
      )}
    </li>
  )
}

function OptionGrid({ options }) {
  return (
    <ul className="grid grid-cols-1 gap-1.5 xl:grid-cols-2">
      {options.map((o) => (
        <OptionRow key={o.key} option={o} />
      ))}
    </ul>
  )
}

// Con `groups` (option_groups del backend) las opciones se muestran en bloques
// separados, p. ej. los splitters de LlamaIndex y los de LangChain.
function OptionList({ options, groups, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  if (!options?.length) return null
  const active = options.filter((o) => o.status === 'active')
  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 self-start rounded text-[12px] font-medium text-muted-foreground hover:text-foreground"
        aria-expanded={open}
      >
        <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
        {open ? 'Ocultar opciones' : `Ver ${options.length} opciones`}
        {!open && groups?.length > 0 && (
          <span>
            {' '}({groups
              .map((g) => `${options.filter((o) => o.group === g.key).length} ${g.label}`)
              .join(' · ')})
          </span>
        )}
        {!open && active.length > 0 && (
          <span className="text-foreground">· en uso: {active.map((o) => o.name).join(', ')}</span>
        )}
      </button>
      {open &&
        (groups?.length ? (
          <div className="flex flex-col gap-4">
            {groups.map((g) => {
              const list = options.filter((o) => o.group === g.key)
              if (!list.length) return null
              return (
                <div key={g.key} className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-semibold">{g.label}</span>
                    <span className="font-mono text-[11px] text-muted-foreground">{list.length}</span>
                    <span className="h-px flex-1 bg-border" />
                  </div>
                  {g.note && (
                    <p className="text-[12px] leading-relaxed text-muted-foreground">{g.note}</p>
                  )}
                  <OptionGrid options={list} />
                </div>
              )
            })}
          </div>
        ) : (
          <OptionGrid options={options} />
        ))}
    </div>
  )
}

// Desplegable "¿Cómo funciona?": los pasos internos de una etapa, con ejemplo
// antes → después (viene de la propia etapa en el backend, ver c_normalize.py).
function HowItWorks({ info }) {
  const [open, setOpen] = useState(false)
  if (!info?.steps?.length) return null
  return (
    <div className="flex flex-col gap-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 self-start rounded text-[12px] font-medium text-muted-foreground hover:text-foreground"
        aria-expanded={open}
      >
        <BookOpen className="size-3.5" />
        {open ? 'Ocultar cómo funciona' : `¿Cómo funciona? (${info.steps.length} pasos)`}
        <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <ol className="flex flex-col gap-2">
            {info.steps.map((step, i) => (
              <li key={step.title} className="rounded-md border border-border px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <span className="mt-px flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-[11px] font-semibold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium">{step.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
                      {step.detail}
                    </p>
                    {step.before && (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <code className="whitespace-pre-wrap rounded border border-destructive/25 bg-destructive/5 px-2 py-1 font-mono text-[11px]">
                          {step.before}
                        </code>
                        <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" />
                        <code className="whitespace-pre-wrap rounded border border-emerald-500/25 bg-emerald-500/5 px-2 py-1 font-mono text-[11px]">
                          {step.after}
                        </code>
                      </div>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ol>
          {info.note && (
            <p className="rounded-md bg-muted/40 px-3 py-2 text-[12px] leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Lo que NO hace: </span>
              {info.note}
            </p>
          )}
        </>
      )}
    </div>
  )
}

function StepCard({ node, index, icon: Icon, defaultOpen, tone = 'default' }) {
  return (
    <div
      className={cn(
        'relative w-full rounded-xl border bg-card p-4 shadow-sm',
        tone === 'end' ? 'border-primary/40' : 'border-border',
      )}
    >
      <div className="flex items-start gap-3">
        {Icon && (
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary">
            <Icon className="size-4.5" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {index != null && (
              <span className="font-mono text-[11px] text-muted-foreground">
                {String(index).padStart(2, '0')}
              </span>
            )}
            <h3 className="text-[15px] font-semibold">{node.title}</h3>
          </div>
          {node.detail && (
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{node.detail}</p>
          )}
          {node.provider && (
            <div className="mt-1.5">
              <ProviderLine provider={node.provider} />
            </div>
          )}
          {node.module && (
            <p className="mt-1.5 break-all font-mono text-[11px] text-muted-foreground/80">
              {node.module}
            </p>
          )}
        </div>
      </div>
      {node.how_it_works && (
        <div className="mt-3 border-t border-border pt-3">
          <HowItWorks info={node.how_it_works} />
        </div>
      )}
      {node.options?.length > 0 && (
        <div className="mt-3 border-t border-border pt-3">
          <OptionList
            options={node.options}
            groups={node.option_groups}
            defaultOpen={defaultOpen}
          />
        </div>
      )}
    </div>
  )
}

// Línea vertical con punta de flecha entre nodos.
function Connector({ className }) {
  return (
    <div className={cn('flex flex-col items-center', className)} aria-hidden>
      <div className="h-6 w-px bg-border" />
      <div className="size-0 border-x-[5px] border-t-[6px] border-x-transparent border-t-border" />
    </div>
  )
}

function Diamond({ question }) {
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex size-20 rotate-45 items-center justify-center rounded-lg border-2 border-primary/50 bg-primary/10 shadow-sm">
        <span className="-rotate-45 text-2xl font-semibold text-primary">?</span>
      </div>
      <p className="max-w-md text-center text-[14px] font-semibold">{question}</p>
    </div>
  )
}

function BranchLabel({ yes }) {
  return (
    <span
      className={cn(
        'rounded-full border px-2.5 py-0.5 text-[11px] font-semibold',
        yes
          ? 'border-sky-500/30 bg-sky-500/10 text-sky-400'
          : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
      )}
    >
      {yes ? 'Sí' : 'No'}
    </span>
  )
}

function Branch({ branch, yes, icon }) {
  return (
    <div className="flex min-w-0 flex-col items-center">
      <div className="h-5 w-px bg-border" aria-hidden />
      <BranchLabel yes={yes} />
      <div className="h-3 w-px bg-border" aria-hidden />
      <StepCard node={branch} icon={icon} defaultOpen={yes} />
      {/* Estira la línea hasta abajo para que ambas ramas se unan a la misma altura. */}
      <div className="min-h-5 w-px flex-1 bg-border" aria-hidden />
    </div>
  )
}

function DecisionNode({ node }) {
  const icon = node.id === 'needs_ocr' ? ScanText : undefined
  return (
    <div className="flex w-full flex-col items-center">
      <Diamond question={node.question} />
      {node.detail && (
        <p className="mt-1 max-w-lg text-center text-[12px] text-muted-foreground">{node.detail}</p>
      )}
      <div className="mt-3 h-4 w-px bg-border" aria-hidden />
      <div className="relative grid w-full grid-cols-2 gap-3 md:gap-6">
        {/* Barras horizontales que abren y cierran la bifurcación (centro de cada columna). */}
        <div className="absolute left-1/4 right-1/4 top-0 h-px bg-border" aria-hidden />
        <div className="absolute bottom-0 left-1/4 right-1/4 h-px bg-border" aria-hidden />
        <Branch branch={node.branches.no} yes={false} />
        <Branch branch={node.branches.yes} yes icon={icon} />
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
      {Object.keys(STATUS).map((k) => (
        <StatusPill key={k} status={k} />
      ))}
      <span className="inline-flex items-center gap-1">
        <KeyRound className="size-3.5 text-amber-400/80" /> requiere API Key
      </span>
      <span className="mx-1 h-4 w-px bg-border" aria-hidden />
      {Object.keys(PRICING).map((k) => (
        <PricePill key={k} pricing={{ kind: k, label: '' }} />
      ))}
      <span>· precios de lista en USD</span>
    </div>
  )
}

export default function PipelineView() {
  const [pipeline, setPipeline] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchPipeline()
      .then(setPipeline)
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <span>{error}</span>
      </div>
    )
  }
  if (!pipeline) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Cargando pipeline…
      </div>
    )
  }

  // Numeración solo para los pasos (las decisiones no llevan número).
  let stepNo = 0
  return (
    <div className="flex flex-col gap-6">
      <Legend />
      <div className="mx-auto flex w-full max-w-7xl flex-col items-center">
        {pipeline.nodes.map((node, i) => (
          <div key={node.id} className="flex w-full flex-col items-center">
            {i > 0 && <Connector />}
            {node.kind === 'decision' ? (
              <DecisionNode node={node} />
            ) : (
              // Los pasos simples se centran a un ancho legible; las ramas usan todo.
              <div className="w-full max-w-4xl">
                <StepCard
                  node={node}
                  index={++stepNo}
                  icon={NODE_ICONS[node.id]}
                  tone={node.kind === 'end' ? 'end' : 'default'}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
