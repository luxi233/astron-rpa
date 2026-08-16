/**
 * electron-builder beforePack hook：打包前确保 resources/appium 预装完成。
 * 挂在 electron-builder.json 上，覆盖本地 build:win 与 CI npx electron-builder 全部构建路径。
 */
const { execFileSync } = require('node:child_process')
const path = require('node:path')

exports.default = async function beforePack() {
  const script = path.join(__dirname, 'install-appium.mjs')
  execFileSync(process.execPath, [script], { stdio: 'inherit' })
}
