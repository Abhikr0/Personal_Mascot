import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import electron from 'vite-plugin-electron'
import renderer from 'vite-plugin-electron-renderer'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    electron([
      {
        entry: 'electron/main.ts',
      },
    ]),
    renderer(),
  ],
  resolve: {
    alias: {
      // Force all imports of pixi-live2d-display to the Cubism4-only ES module build
      // This avoids the default entry which requires the Cubism 2 runtime (live2d.min.js)
      'pixi-live2d-display': path.resolve(
        import.meta.dirname,
        'node_modules/pixi-live2d-display/dist/cubism4.es.js'
      ),
    },
  },
})
