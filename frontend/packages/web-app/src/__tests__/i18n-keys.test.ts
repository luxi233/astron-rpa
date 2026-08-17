import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/** 从 cwd 逐级向上查找仓库内文件(兼容从根/包目录两种方式启动 vitest) */
function findRepoFile(rel: string): string {
  let dir = process.cwd()
  for (let i = 0; i < 6; i++) {
    const candidate = resolve(dir, rel)
    if (existsSync(candidate))
      return candidate
    dir = dirname(dir)
  }
  throw new Error(`repo file not found: ${rel}`)
}

function loadLocale(name: string): Record<string, any> {
  return JSON.parse(readFileSync(findRepoFile(`locales/${name}`), 'utf-8'))
}

/** 递归收集叶子键路径 */
function flatKeys(obj: Record<string, any>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const path = prefix ? `${prefix}.${k}` : k
    return typeof v === 'object' && v !== null && !Array.isArray(v)
      ? flatKeys(v, path)
      : [path]
  })
}

const zh = loadLocale('zh-CN.json')
const en = loadLocale('en-US.json')

describe('i18n - 本次新增键', () => {
  it('zh-CN 与 en-US 均包含新增的触发方式/日志导出键', () => {
    const newKeys = [
      'record.selectTriggerType',
      'record.allTriggerType',
      'record.manualRun',
      'record.taskRun',
      'exportLog',
      'noLogToExport',
      'exportLogFailed',
    ]
    const zhKeys = new Set(flatKeys(zh))
    const enKeys = new Set(flatKeys(en))
    for (const key of newKeys) {
      expect(zhKeys, `zh-CN 缺少 ${key}`).toContain(key)
      expect(enKeys, `en-US 缺少 ${key}`).toContain(key)
    }
  })
})

describe('i18n - record 命名空间中英文对齐', () => {
  it('record.* 键集合一致(防止后续增删键时漏翻译)', () => {
    const zhRecord = flatKeys(zh.record ?? {})
    const enRecord = flatKeys(en.record ?? {})
    expect(new Set(enRecord)).toEqual(new Set(zhRecord))
  })
})
