import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5555,
    host: true,
    proxy: {
      '/api': {
        target: 'http://backend:9555',
        changeOrigin: true
      }
    }
  }
})