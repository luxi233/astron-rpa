import { spawn } from 'node:child_process'
import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'

import treeKill from 'tree-kill'

import logger from './log'
import { appiumHome } from './path'

// 与 Python 端 Phone.connect 的 appium_server 默认值保持一致
export const APPIUM_PORT = 4723
const APPIUM_HOST = '127.0.0.1'
const READY_TIMEOUT = 30_000
const POLL_INTERVAL = 500

let appiumProcess: import('node:child_process').ChildProcess | null = null
let startingPromise: Promise<boolean> | null = null

function appiumMainJs(): string | null {
  const main = path.join(appiumHome, 'node_modules', 'appium', 'build', 'lib', 'main.js')
  return fs.existsSync(main) ? main : null
}

/**
 * 探测 Appium server 是否存活（GET /status）
 */
export function isAppiumAlive(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      { host: APPIUM_HOST, port: APPIUM_PORT, path: '/status', timeout: 1500 },
      (res) => {
        res.resume()
        resolve(res.statusCode === 200)
      },
    )
    req.on('timeout', () => {
      req.destroy()
      resolve(false)
    })
    req.on('error', () => resolve(false))
  })
}

function startAppiumProcess(mainJs: string) {
  const child = spawn(
    process.execPath,
    [mainJs, '--port', String(APPIUM_PORT), '--address', APPIUM_HOST, '--log-level', 'info'],
    {
      env: { ...process.env, ELECTRON_RUN_AS_NODE: '1', APPIUM_HOME: appiumHome },
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )

  child.stdout?.on('data', (data: Buffer) => {
    for (const line of data.toString().split('\n')) {
      const trimmed = line.trim()
      if (trimmed) logger.info(`[appium] ${trimmed}`)
    }
  })
  child.stderr?.on('data', (data: Buffer) => {
    for (const line of data.toString().split('\n')) {
      const trimmed = line.trim()
      if (trimmed) logger.warn(`[appium] ${trimmed}`)
    }
  })
  child.once('close', (code) => {
    logger.info(`appium server exited with code ${code}`)
    if (appiumProcess === child) appiumProcess = null
  })
  child.once('error', (error) => {
    logger.error(`appium server start failed: ${error.message}`)
    if (appiumProcess === child) appiumProcess = null
  })

  appiumProcess = child
}

async function waitUntilAlive(deadline: number): Promise<boolean> {
  while (Date.now() < deadline) {
    // 进程中途退出直接失败，不再空等
    if (!appiumProcess) return false
    if (await isAppiumAlive()) return true
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL))
  }
  return false
}

/**
 * 确保内置 Appium server 运行（幂等）：
 * 已存活 → 复用（包括用户自装的 Appium）；未打包/预装缺失 → 告警跳过
 */
export async function ensureAppiumServer(): Promise<boolean> {
  if (await isAppiumAlive()) {
    logger.info('appium server already running, reuse it')
    return true
  }

  const mainJs = appiumMainJs()
  if (!mainJs) {
    logger.warn(`builtin appium not found at ${appiumHome}, phone appium mode needs an external appium server`)
    return false
  }

  if (startingPromise) return startingPromise

  startingPromise = (async () => {
    logger.info(`starting builtin appium server on ${APPIUM_HOST}:${APPIUM_PORT}`)
    startAppiumProcess(mainJs)
    const ok = await waitUntilAlive(Date.now() + READY_TIMEOUT)
    if (ok) logger.info('appium server ready')
    else logger.error(`appium server not ready within ${READY_TIMEOUT / 1000}s`)
    return ok
  })().finally(() => {
    startingPromise = null
  })

  return startingPromise
}

/**
 * 停止内置 Appium server（杀进程树，driver 子进程一并退出）
 */
export function stopAppiumServer(): Promise<void> {
  return new Promise((resolve) => {
    const child = appiumProcess
    appiumProcess = null
    if (!child || child.killed || child.exitCode !== null) {
      resolve()
      return
    }
    treeKill(child.pid!, 'SIGTERM', (error) => {
      if (error) logger.warn(`appium server tree-kill failed: ${error.message}`)
      resolve()
    })
  })
}
