/**
 * 预装 Appium 运行时到 <repo>/resources/appium，随客户端打包（开箱即用）。
 *
 * - 安装 appium 主包 + appium-uiautomator2-driver 到 resources/appium/node_modules
 * - Appium 2.x 启动时通过 APPIUM_HOME 环境变量从该目录发现 driver
 * - electron-builder 的 extraFiles 会把整个 resources/ 打进安装包
 *
 * 幂等：重复执行只做增量校验，node_modules 已存在时 npm install 秒级完成。
 */
import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// 钉住已验证版本保证可重复构建（可环境变量覆盖）；sharp 等原生依赖随宿主平台安装
const APPIUM_VERSION = process.env.APPIUM_VERSION || '2.19.0'
const UIAUTOMATOR2_DRIVER_VERSION = process.env.UIAUTOMATOR2_DRIVER_VERSION || '3.10.0'

const electronAppDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const repoRoot = path.resolve(electronAppDir, '..', '..', '..')
const appiumHome = path.join(repoRoot, 'resources', 'appium')

// 产出 Windows 安装包必须用 Windows 宿主构建：npm 原生依赖（sharp 等）按宿主平台安装，
// 非 Windows 宿主上预装的 node_modules 会导致打包产物在 Windows 上损坏
if (process.env.CI !== 'true' && process.platform !== 'win32') {
  console.warn('[install-appium] WARNING: host is not win32; run appium install on a Windows host before building Windows installers, or native deps (sharp) will not match the target platform')
}

const mainJs = path.join(appiumHome, 'node_modules', 'appium', 'build', 'lib', 'main.js')
const driverPkg = path.join(appiumHome, 'node_modules', 'appium-uiautomator2-driver', 'package.json')

function isInstalled() {
  return fs.existsSync(mainJs) && fs.existsSync(driverPkg)
}

if (process.argv.includes('--check')) {
  process.exit(isInstalled() ? 0 : 1)
}

fs.mkdirSync(appiumHome, { recursive: true })
fs.writeFileSync(
  path.join(appiumHome, 'package.json'),
  JSON.stringify({ name: 'astron-appium-runtime', private: true, version: '1.0.0' }, null, 2),
)

if (isInstalled() && !process.argv.includes('--force')) {
  console.log(`[install-appium] already installed at ${appiumHome}, skip`)
  process.exit(0)
}

console.log(`[install-appium] installing appium@${APPIUM_VERSION} + appium-uiautomator2-driver@${UIAUTOMATOR2_DRIVER_VERSION} -> ${appiumHome}`)
execSync(
  `npm install --omit=dev --no-audit --no-fund --prefer-offline appium@${APPIUM_VERSION} appium-uiautomator2-driver@${UIAUTOMATOR2_DRIVER_VERSION}`,
  { cwd: appiumHome, stdio: 'inherit' },
)

if (!isInstalled()) {
  console.error('[install-appium] install finished but entry files missing, please retry with --force')
  process.exit(1)
}
console.log('[install-appium] done')
