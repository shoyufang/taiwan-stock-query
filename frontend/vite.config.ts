import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    // 本機開發：API 轉到本機 uvicorn（cd backend && uvicorn app.main:app --port 8000）
    proxy: { '/api': 'http://127.0.0.1:8000', '/ws': { target: 'ws://127.0.0.1:8000', ws: true } },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
