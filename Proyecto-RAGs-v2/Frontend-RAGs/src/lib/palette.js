// Colores para distinguir chunks/documentos, ligados a los tokens de tema
// (--chart-1..5), de modo que funcionan igual en claro y oscuro.
export const CHUNK_VARS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
]

export function chunkColor(index) {
  return CHUNK_VARS[index % CHUNK_VARS.length]
}
