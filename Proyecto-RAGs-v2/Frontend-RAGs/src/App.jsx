import { useEffect, useMemo, useState } from 'react'
import { FileText, Scissors, Boxes, Database, AlertTriangle, Workflow } from 'lucide-react'
import { fetchSplitters, fetchLoaders, fetchEmbedders, fetchVectorStores } from './api'
import Sidebar from './components/Sidebar'
import { cn } from '@/lib/utils'
import SplitterView from './components/SplitterView'
import LoaderView from './components/LoaderView'
import EmbedderView from './components/EmbedderView'
import VectorStoreView from './components/VectorStoreView'
import PipelineView from './components/PipelineView'

const TAB_INFO = {
  pipeline: {
    icon: Workflow,
    title: 'Pipeline de ingesta',
    subtitle: 'El flujo completo de arriba hacia abajo, con las opciones y el precio de cada etapa.',
  },
  splitters: {
    icon: Scissors,
    title: 'Text Splitters',
    subtitle: 'Coloca un documento y observa cómo lo divide en chunks cada técnica de LlamaIndex.',
  },
  loaders: {
    icon: FileText,
    title: 'Document Loaders',
    subtitle: 'Sube un archivo y compara cómo extrae el texto cada Reader — de la peor a la mejor opción.',
  },
  embedders: {
    icon: Boxes,
    title: 'Embeddings · Indexación',
    subtitle: 'Indexa un documento con el modelo de embedding elegido y consulta el índice vectorial.',
  },
  vectorstores: {
    icon: Database,
    title: 'Vector Store · Fuerza Bruta vs. ANN',
    subtitle: 'Compara motores de índice: coste de construir, velocidad de búsqueda y recall vs. el exacto.',
  },
}

export default function App() {
  const [activeTab, setActiveTab] = useState('pipeline')
  const [splitters, setSplitters] = useState([])
  const [loaders, setLoaders] = useState([])
  const [embedders, setEmbedders] = useState([])
  const [vectorstores, setVectorstores] = useState([])
  const [selSplitter, setSelSplitter] = useState(null)
  const [selLoader, setSelLoader] = useState(null)
  const [selEmbedder, setSelEmbedder] = useState(null)
  const [selStore, setSelStore] = useState(null)
  const [error, setError] = useState(null)

  // Cargar los tres catálogos al iniciar.
  useEffect(() => {
    fetchSplitters()
      .then((list) => {
        setSplitters(list)
        if (list.length) setSelSplitter(list[0].key)
      })
      .catch((e) => setError(e.message))
    fetchLoaders()
      .then((list) => {
        setLoaders(list)
        if (list.length) setSelLoader(list[0].key)
      })
      .catch((e) => setError(e.message))
    fetchEmbedders()
      .then((list) => {
        setEmbedders(list)
        // Preseleccionar el que el backend resolvería en automático (is_default =
        // el primero con API key presente), no el primero del catálogo a ciegas.
        const pick = list.find((e) => e.is_default) || list.find((e) => e.available) || list[0]
        if (pick) setSelEmbedder(pick.key)
      })
      .catch((e) => setError(e.message))
    fetchVectorStores()
      .then((list) => {
        setVectorstores(list)
        if (list.length) setSelStore(list[0].key)
      })
      .catch((e) => setError(e.message))
  }, [])

  // Seleccionar un ítem también decide qué panel se muestra en el área principal.
  function handleSelectLoader(key) {
    setSelLoader(key)
    setActiveTab('loaders')
  }
  function handleSelectSplitter(key) {
    setSelSplitter(key)
    setActiveTab('splitters')
  }
  function handleSelectEmbedder(key) {
    setSelEmbedder(key)
    setActiveTab('embedders')
  }
  function handleSelectStore(key) {
    setSelStore(key)
    setActiveTab('vectorstores')
  }

  const selectedSplitter = useMemo(
    () => splitters.find((s) => s.key === selSplitter) || null,
    [splitters, selSplitter],
  )
  const selectedLoader = useMemo(
    () => loaders.find((l) => l.key === selLoader) || null,
    [loaders, selLoader],
  )
  const selectedEmbedder = useMemo(
    () => embedders.find((e) => e.key === selEmbedder) || null,
    [embedders, selEmbedder],
  )
  const selectedStore = useMemo(
    () => vectorstores.find((s) => s.key === selStore) || null,
    [vectorstores, selStore],
  )
  // Máximo de calidad derivado del propio catálogo (no hardcodeado): si mañana
  // se agrega un loader de calidad 7, las barras escalan solas.
  const maxQuality = useMemo(
    () => (loaders.length ? Math.max(...loaders.map((l) => l.quality ?? 1)) : 6),
    [loaders],
  )

  const info = TAB_INFO[activeTab]
  const HeaderIcon = info.icon

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar
        loaders={loaders}
        splitters={splitters}
        embedders={embedders}
        vectorstores={vectorstores}
        maxQuality={maxQuality}
        selLoader={selLoader}
        selSplitter={selSplitter}
        selEmbedder={selEmbedder}
        selStore={selStore}
        activeTab={activeTab}
        onSelectLoader={handleSelectLoader}
        onSelectSplitter={handleSelectSplitter}
        onSelectEmbedder={handleSelectEmbedder}
        onSelectStore={handleSelectStore}
        onSelectPipeline={() => setActiveTab('pipeline')}
      />

      <main className="relative flex-1 min-w-0">
        {/* Glow superior sutil, estilo dev-tool */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-64 opacity-60"
          style={{
            background:
              'radial-gradient(60% 100% at 50% 0%, color-mix(in oklch, var(--primary) 18%, transparent), transparent 70%)',
          }}
        />

        {/* El diagrama del pipeline necesita más ancho que las demás pestañas. */}
        <div
          className={cn(
            'relative mx-auto px-6 py-8 md:px-10',
            activeTab === 'pipeline' ? 'max-w-[1600px]' : 'max-w-5xl',
          )}
        >
          <header className="mb-8">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl border border-border bg-card text-primary shadow-sm">
                <HeaderIcon className="size-5" />
              </span>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">{info.title}</h1>
                <p className="mt-0.5 text-sm text-muted-foreground">{info.subtitle}</p>
              </div>
            </div>
          </header>

          {error && (
            <div className="mb-6 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {activeTab === 'pipeline' && <PipelineView />}
          {activeTab === 'loaders' && (
            <LoaderView selected={selectedLoader} maxQuality={maxQuality} />
          )}
          {activeTab === 'splitters' && (
            <SplitterView selected={selectedSplitter} loader={selectedLoader} />
          )}
          {activeTab === 'embedders' && <EmbedderView selected={selectedEmbedder} />}
          {activeTab === 'vectorstores' && (
            <VectorStoreView
              stores={vectorstores}
              embedders={embedders}
              selected={selectedStore}
            />
          )}
        </div>
      </main>
    </div>
  )
}
