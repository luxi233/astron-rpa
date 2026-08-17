import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import { defineConfig } from 'vitest/config'

const baseSrc = fileURLToPath(new URL('./src', import.meta.url))

export default defineConfig({
  plugins: [vue(), vueJsx()],
  resolve: {
    alias: [
      { find: '@', replacement: baseSrc },
      { find: 'dayjs', replacement: 'dayjs/esm' },
      { find: /^dayjs\/locale/, replacement: 'dayjs/esm/locale' },
      { find: /^dayjs\/plugin/, replacement: 'dayjs/esm/plugin' },
      { find: 'lodash', replacement: 'lodash-es' },
    ],
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
