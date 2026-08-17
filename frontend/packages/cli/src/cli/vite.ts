import { federation } from '@module-federation/vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import type { InlineConfig, PluginOption, ViteDevServer } from 'vite'
import { build, createServer } from 'vite'

import { loadRpaConfig } from '../config'

// const __filename = fileURLToPath(import.meta.url)
// const __dirname = path.dirname(__filename)

async function createViteServer(inlineConfig: InlineConfig): Promise<ViteDevServer> {
  const error = console.error
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string'
      && args[0].includes('WebSocket server error:')
    ) {
      return
    }
    error(...args)
  }

  const server = await createServer(inlineConfig)

  console.error = error
  return server
}

export async function createBuildServer(options: { dev?: boolean }): Promise<void> {
  const root = process.cwd()
  const command = options.dev ? 'serve' : 'build'
  const mode = options.dev ? 'development' : 'production'

  const userConfig = await loadRpaConfig(root, command, mode)
  const remoteName = userConfig?.name || 'remote';

  const config: InlineConfig = {
    build: {
      modulePreload: false,
    },
    plugins: [
      federation({
        shared: ['vue', 'vue-router'],
        ...userConfig,
        name: remoteName,
        manifest: true,
        publicPath: options.dev ? undefined : `rpa://extensions/${remoteName}/`,
        exposes: {
          './index': './src/index.ts',
        },
      }),
      // 插件包依赖嵌套的 vite/rolldown 类型实例，结构兼容根 vite，断言对齐
      vue() as PluginOption,
      vueJsx() as PluginOption,
    ],
    resolve: {
      alias: {
        // '@': path.resolve(__dirname, 'src'),
      },
    },
  }

  if (options.dev) {
    const viteServer = await createViteServer(config)

    await viteServer.listen()

    viteServer.printUrls()
    viteServer.bindCLIShortcuts({ print: true })
  }
  else {
    await build(config)
  }
}
