import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    outDir: '../dist/gallery',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Split Three.js + R3F into a separate lazy chunk
          'three-vendor': ['three', '@react-three/fiber', '@react-three/drei'],
        },
      },
    },
    // Allow the 3D vendor bundle to be large without warnings
    chunkSizeWarningLimit: 1500,
  },
})
