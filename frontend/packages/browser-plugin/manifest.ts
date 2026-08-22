/** @format */
import { readFileSync, writeFileSync } from 'node:fs'

export function generateManifest(mode: string, environment) {
  console.log('Generating manifest.json...')
  const packageJson = readFileSync('./package.json', 'utf-8')
  const { version } = JSON.parse(packageJson)
  const isFirefox = mode === 'firefox'
  // 修复: 本地无 .env 时 VITE_* 为 undefined, description 会拼出 "undefined-xxx" 污染提交产物;
  // 全部字段加兜底, 且 description 不带模式后缀(与历史发布产物一致)
  const appName = environment.VITE_APP_NAME || 'Browser-Plugin'
  const appDescription = environment.VITE_APP_DESCRIPTION || appName
  const appHomePage = environment.VITE_APP_HOMEPAGE || 'https://www.iflyrpa.com'
  let manifest = {
    manifest_version: 3,
    name: appName,
    description: appDescription,
    homepage_url: appHomePage,
    version,
    icons: {
      16: 'static/icon_16.png',
      48: 'static/icon_48.png',
      128: 'static/icon_128.png',
    },
    background: {
      service_worker: 'background.js',
      type: 'module',
    },
    host_permissions: ['<all_urls>'],
    content_scripts: [
      {
        all_frames: true,
        matches: ['http://*/*', 'https://*/*', 'file://*/*', 'ftp://*/*'],
        js: ['content.js'],
        css: ['rpa.css'],
        run_at: 'document_start',
        match_about_blank: false,
        world: 'ISOLATED',
      },
    ],
    content_security_policy: {
      extension_pages: 'script-src \'self\'; object-src \'self\';',
      sandbox: 'sandbox allow-scripts allow-forms allow-popups allow-modals; script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; child-src \'self\';',
    },
    permissions: [
      'alarms',
      'nativeMessaging',
      'debugger',
      'tabs',
      'activeTab',
      // 'contextMenus',
      'webNavigation',
      'cookies',
      'storage',
      // 'notifications',
      // 'tabCapture',
      'scripting',
      // 'userScripts',
      'management',
    ],
  }

  if (isFirefox) {
    const permission = manifest.permissions.filter(item => item !== 'debugger')
    const manifestFirefox = {
      manifest_version: 2,
      background: {
        scripts: ['background.js'],
      },
      description: `${appDescription}-Firefox`,
      content_security_policy: 'script-src \'none\' \'unsafe-eval\';',
      browser_specific_settings: {
        gecko: {
          id: environment.VITE_FIREFOXID,
          strict_min_version: '58.0',
        },
      },
      permissions: [...permission, '<all_urls>', 'webRequest', 'webRequestBlocking'],
    }
    // @ts-expect-error firefox specific
    manifest = { ...manifest, ...manifestFirefox }
  }

  writeFileSync('./public/manifest.json', JSON.stringify(manifest, null, 2))
  console.log('manifest.json generated successfully.')
}
