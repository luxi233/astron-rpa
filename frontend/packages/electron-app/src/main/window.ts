import path from 'node:path'

import type { CreateWindowOptions } from '@rpa/shared/platform'
import { app, BrowserWindow, screen } from 'electron'
import { isUndefined } from 'lodash'

import { APP_ICON_PATH, MAIN_WINDOW_LABEL } from './config'
import logger from './log'
import { resourcePath } from './path'

export const WindowStack: Map<string, BrowserWindow> = new Map()

export function getWindowFromLabel(label: string) {
  return WindowStack.get(label)
}

export function getMainWindow() {
  return getWindowFromLabel(MAIN_WINDOW_LABEL)
}

export function electronInfo(win: BrowserWindow) {
  const electronVersion = process.versions.electron
  const electronInfo = JSON.stringify({
    electronVersion,
    appPath: app.getPath('exe'),
    userDataPath: app.getPath('userData'),
    appVersion: app.getVersion(),
    release: process.getSystemVersion(),
    arch: process.arch,
    platform: process.platform,
    preload: path.join(__dirname, '../preload/index.js'),
    resourcePath,
  })
  win.webContents.send('electron-info', electronInfo)
}

function createWindow(options: Electron.BrowserWindowConstructorOptions, label?: string) {
  const win = new BrowserWindow(options)

  if (label) {
    WindowStack.set(label, win)
  }

  return win
}

/**
 * 渲染进程崩溃自愈。
 * 系统内存提交额度耗尽（物理内存 + 页面文件用光）时 Chromium 会杀掉渲染进程（OOM），
 * 此时窗口壳还在但内容变成白屏且无法操作。这里监听崩溃/加载失败事件并自动重载恢复。
 */
export function enableCrashRecovery(win: BrowserWindow, reloadUrl: string) {
  const MAX_RELOAD = 3
  let reloadCount = 0

  const reload = (reason: string) => {
    if (win.isDestroyed())
      return
    if (reloadCount >= MAX_RELOAD) {
      logger.error(`crash recovery: reload 超过上限(${MAX_RELOAD})，放弃重载`)
      return
    }
    reloadCount += 1
    logger.warn(`crash recovery: ${reason}，${1}s 后重载 ${reloadUrl}（第 ${reloadCount} 次）`)
    setTimeout(() => {
      if (win.isDestroyed())
        return
      win.loadURL(reloadUrl).then(() => electronInfo(win)).catch(err => logger.error('crash recovery reload failed:', err.toString()))
    }, 1000)
  }

  // 重载成功后重置计数，避免长会话中累计耗尽自愈次数
  win.webContents.on('did-finish-load', () => {
    reloadCount = 0
  })

  win.webContents.on('render-process-gone', (_event, details) => {
    logger.warn(`render-process-gone reason=${details.reason} exitCode=${details.exitCode}`)
    if (details.reason === 'clean-exit')
      return
    // crashed / oom / killed / abnormal-exit 等均尝试自愈
    reload(`渲染进程退出(${details.reason})`)
  })

  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, _validatedURL, isMainFrame) => {
    // 忽略子框架失败与导航中断（ERR_ABORTED = -3，页面跳转时必然触发）
    if (!isMainFrame || errorCode === -3)
      return
    logger.warn(`did-fail-load errorCode=${errorCode} ${errorDescription}`)
    reload(`页面加载失败(${errorCode})`)
  })

  win.webContents.on('unresponsive', () => {
    logger.warn('renderer unresponsive')
  })
  win.webContents.on('responsive', () => {
    logger.info('renderer responsive')
  })
}

export function createMainWindow() {
  const mainWindowOptions: Electron.BrowserWindowConstructorOptions = {
    title: 'iflyrpa',
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    width: 1280,
    height: 750,
    icon: APP_ICON_PATH,
    resizable: true,
    center: true,
    show: false,
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
    },
  }

  return createWindow(mainWindowOptions, MAIN_WINDOW_LABEL)
}

export function createSubWindow(options: CreateWindowOptions) {
  logger.info('createSubWindow', JSON.stringify(options))
  const {
    width = 800,
    height = 600,
    url,
    offset = 0,
    position,
    x: _x,
    y: _y,
    ...restOptions
  } = options

  // 跟随鼠标所在显示器(而非固定主屏), 多屏时子窗口出现在用户操作的屏幕上;
  // 非主屏 workArea 原点可能非 (0,0), 各方位需叠加 workArea.x/y 偏移
  const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint())
  const { x: areaX, y: areaY, width: screenWidth, height: screenHeight } = display.workArea

  let x: number | undefined = _x
  let y: number | undefined = _y

  switch (position) {
    case 'left_top':
      x = areaX + 2
      y = areaY + 2
      break
    case 'right_top':
      x = areaX + screenWidth - width - 2
      y = areaY + 2
      break
    case 'left_bottom':
      x = areaX + 2
      y = areaY + screenHeight - height - 2
      break
    case 'right_bottom':
      x = areaX + screenWidth - width - 2
      y = areaY + screenHeight - height - 2
      break
    case 'top_center':
      x = areaX + Math.round((screenWidth - width) / 2)
      y = areaY + 2
      break
    case 'center':
      x = areaX + Math.round((screenWidth - width) / 2)
      y = areaY + Math.round((screenHeight - height) / 2)
      break
    case 'right_center':
      x = areaX + screenWidth - width - offset
      y = areaY + screenHeight / 2 - height / 2
      break
    default:
      break
  }

  const subWindowOptions: Electron.BrowserWindowConstructorOptions = {
    ...restOptions,
    ...(isUndefined(x) && isUndefined(y) ? { center: true } : { x, y }),
    width,
    height,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
    },
    icon: APP_ICON_PATH,
    frame: false,
  }

  const window = createWindow(subWindowOptions, options.label)
  enableCrashRecovery(window, url)
  window.loadURL(url).then(() => electronInfo(window)).catch(() => logger.error('Failed to load URL'))
  window.on('ready-to-show', () => {
    if (options?.show !== false) {
      window.show()
    }
    window.focus()
  })

  return window
}
