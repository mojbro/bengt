import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 3500,
    // Dev-only: accept any Host header. We access this from multiple hostnames
    // on a LAN (laptop, maxi.local, phone). Production serves a static build
    // behind its own server, so this relaxation doesn't apply there.
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://backend:3501',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
