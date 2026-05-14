import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy publish index JSON requests to a local file server if needed
  },
  build: {
    outDir: '../dist/gallery',
    emptyOutDir: true,
  },
})
