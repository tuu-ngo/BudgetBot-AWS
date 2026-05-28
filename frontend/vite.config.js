import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward all /api-path calls to the FastAPI backend on :8000
      '/upload':       'http://localhost:8000',
      '/summary':      'http://localhost:8000',
      '/transactions': 'http://localhost:8000',
      '/chat':         'http://localhost:8000',
      '/budget-caps':  'http://localhost:8000',
      '/budget':       'http://localhost:8000',
      '/users':        'http://localhost:8000',
      '/files':        'http://localhost:8000',
      '/health':       'http://localhost:8000',
    },
  },
})
