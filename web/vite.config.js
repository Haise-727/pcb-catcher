import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Dev server stays on loopback for the same reason the API does: design
    // files are the customer's confidential IP and must not reach the LAN.
    host: '127.0.0.1',
    port: 5173,
  },
})
