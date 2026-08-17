import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * 后端 RobotExecuteRecordDao.xml 的静态守护测试。
 *
 * 背景: 本仓库前端 CI 无 Java/Maven 环境, 无法运行 JUnit; 此处以 DOMParser
 * 解析 mapper XML, 守护 "触发方式筛选" 相关动态 SQL 的结构正确性,
 * 防止后续改动破坏良构性或误删条件。运行时行为由
 * backend/robot-service/src/test/java/.../RobotExecuteRecordDaoSqlTest.java
 * (MyBatis getBoundSql 断言) 在有 Maven 的环境覆盖。
 */
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

const mapperPath = findRepoFile(
  'backend/robot-service/src/main/java/com/iflytek/rpa/robot/dao/RobotExecuteRecordDao.xml',
)

const dtoPath = findRepoFile(
  'backend/robot-service/src/main/java/com/iflytek/rpa/robot/entity/dto/ExecuteRecordDto.java',
)

const xml = readFileSync(mapperPath, 'utf-8')
// jsdom environment 自带全局 DOMParser(支持 application/xml), 无需显式引入 jsdom 包
const doc = new DOMParser().parseFromString(xml, 'application/xml')

/** 按语句 id 查找 mapper 节点(XML 文档下 CSS # 选择器不可靠, 用属性遍历) */
function findStatement(id: string): Element | null {
  return [...doc.getElementsByTagName('*')].find(e => e.getAttribute('id') === id) ?? null
}

function selectText(id: string): string {
  const node = findStatement(id)
  return node ? (node.textContent ?? '') : ''
}

describe('robotExecuteRecordDao.xml - 良构性', () => {
  it('xML 可被解析且无 parsererror', () => {
    expect(doc.querySelector('parsererror')).toBeNull()
  })

  it('原有全部语句未被破坏', () => {
    const allIds = [
      'getExecuteRecordList',
      'getRecordByExecuteIdList',
      'robotOverview',
      'getExecuteLog',
      'getExecuteRecord',
      'insertExecuteRecord',
      'updateExecuteRecord',
      'batchDeleteByTaskExecuteIds',
      'deleteRobotExecuteRecords',
    ]
    for (const id of allIds) {
      expect(findStatement(id), `缺少语句 ${id}`).not.toBeNull()
    }
  })
})

describe('robotExecuteRecordDao.xml - 触发方式筛选(triggerType)', () => {
  const sql = selectText('getExecuteRecordList')

  function getTriggerTypeIfs(): Element[] {
    const stmt = findStatement('getExecuteRecordList')!
    return [...stmt.getElementsByTagName('if')]
      .filter(e => (e.getAttribute('test') ?? '').includes('triggerType'))
  }

  it('manual 条件: task_execute_id 为空', () => {
    const manualIf = getTriggerTypeIfs().find(e => (e.getAttribute('test') ?? '').includes('manual'))
    expect(manualIf, '缺少 manual 的 <if>').toBeTruthy()
    const text = (manualIf?.textContent ?? '').replace(/\s+/g, ' ').trim()
    expect(text).toContain('rer.task_execute_id is null')
    expect(text).toContain(`rer.task_execute_id = ''`)
  })

  it('task 条件: task_execute_id 非空', () => {
    const taskIf = getTriggerTypeIfs().find(e => (e.getAttribute('test') ?? '').includes('task'))
    expect(taskIf, '缺少 task 的 <if>').toBeTruthy()
    const text = (taskIf?.textContent ?? '').replace(/\s+/g, ' ').trim()
    expect(text).toContain('rer.task_execute_id is not null')
    expect(text).toContain(`rer.task_execute_id != ''`)
  })

  it('两个条件均含 null 前置判断(空值不过滤)', () => {
    const ifs = getTriggerTypeIfs()
    expect(ifs).toHaveLength(2)
    for (const node of ifs) {
      expect(node.getAttribute('test')).toContain('entity.triggerType != null')
    }
  })

  it('原有筛选与排序仍在同一条语句中', () => {
    expect(sql).toContain('upper(re.name) like')
    expect(sql).toContain('rer.result = #{entity.result}')
    expect(findStatement('getExecuteRecordList')!.getElementsByTagName('choose').length).toBeGreaterThan(0)
    expect(sql).toContain('order by start_time desc')
  })
})

describe('executeRecordDto 与 mapper 联动', () => {
  it('dTO 中存在 triggerType 字段(防 XML 条件指向已删除字段)', () => {
    const dto = readFileSync(dtoPath, 'utf-8')
    expect(dto).toMatch(/private\s+String\s+triggerType\s*;/)
  })
})
