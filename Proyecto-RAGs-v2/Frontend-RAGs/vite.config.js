import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // 5174 para no chocar con otras apps de Vite que usan el 5173 por defecto.
    // strictPort: falla claro si el 5174 también está ocupado, en vez de saltar
    // a otro puerto en silencio.
    port: 5174,
    strictPort: true,
    // Proxy hacia el backend FastAPI (env conda RAG-Pipeline) para evitar líos de CORS en dev.
    proxy: {
      '/api': {
        target: 'http://localhost:8005',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
