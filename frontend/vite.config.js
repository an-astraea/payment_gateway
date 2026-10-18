import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// In development, /api calls are forwarded to FastAPI on port 8000.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
