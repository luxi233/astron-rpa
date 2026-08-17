import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// ---- mock 依赖（必须在 import 被测模块前声明, vitest 会 hoist） ----
vi.mock('i18next-vue', () => ({
  useTranslation: () => ({ t: (k: string) => k, i18next: { language: 'zh-CN' } }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@rpa/components', () => ({
  Icon: { name: 'Icon', props: ['name', 'size'], render() { return null } },
}))

vi.mock('@/api/record', () => ({
  getlogs: vi.fn(),
}))

vi.mock('@/platform', () => ({
  utilsManager: {
    saveFile: vi.fn(async () => true),
    playVideo: vi.fn(),
  },
}))

vi.mock('@/views/Home/components/OperMenu.vue', () => ({
  default: { name: 'OperMenu', props: ['row', 'moreOpts'], render() { return null } },
}))

vi.mock('@/views/Home/components/StatusCircle.vue', () => ({
  default: { name: 'StatusCircle', props: ['type'], render() { return null } },
}))

vi.mock('@/views/Home/pages/hooks/useCommonOperate.tsx', () => ({
  useCommonOperate: () => ({
    handleCheck: vi.fn(),
    handleOpenDataTable: vi.fn(),
  }),
}))

vi.mock('@/views/Home/components/RecordTable/hooks/useRecordOperation.tsx', () => ({
  default: () => ({
    rowSelection: {},
    getTableData: vi.fn(),
    batchDelete: vi.fn(),
  }),
}))

const { getlogs: getlogsRaw } = await import('@/api/record')
const getlogs = vi.mocked(getlogsRaw)
const { utilsManager: utilsManagerRaw } = await import('@/platform')
const utilsManager = vi.mocked(utilsManagerRaw, true)
const { message } = await import('ant-design-vue')
const useRecordTableColumns = (await import('../useRecordTableColumns.tsx')).default

/** 从 oper 列的 customRender 结果 VNode 中提取 moreOpts 菜单配置 */
function getMoreOpts(props: { robotId?: string, taskId?: string } = {}) {
  const { columns } = useRecordTableColumns(props)
  const operColumn: any = columns.find(c => c.key === 'oper')
  const vnode = operColumn.customRender({ record: {} })
  return vnode.props.moreOpts as Array<{ key: string, text: string, clickFn: (record: any) => void, disableFn?: (record: any) => boolean }>
}

describe('useRecordTableColumns - 导出日志', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const record = {
    executeId: 'exe-001',
    robotName: '测试应用',
    startTime: '2026-08-17 10:00:00',
  }

  function fakeLogs() {
    return JSON.stringify([
      {
        event_time: 1755396000,
        data: { log_level: 'info', process: 'main', line: 12, msg_str: '流程开始' },
      },
      {
        event_time: 1755396060,
        data: { log_level: 'error', process: 'flow1', line: 34, msg_str: '执行失败', error_traceback: 'Traceback (most recent call last):\n  File "x.py", line 1' },
      },
    ])
  }

  it('成功导出: 调用 getlogs 并将格式化内容写入文件', async () => {
    getlogs.mockResolvedValue({ data: fakeLogs() })
    const exportOpt = getMoreOpts().find(o => o.key === 'exportLog')!
    expect(exportOpt).toBeTruthy()

    await exportOpt.clickFn(record)

    expect(getlogs).toHaveBeenCalledWith({ executeId: 'exe-001' })
    expect(utilsManager.saveFile).toHaveBeenCalledTimes(1)

    const [fileName, content] = (utilsManager.saveFile as any).mock.calls[0]
    // 文件名格式: runlog-{应用名}-{yyyyMMdd-HHmmss}.txt
    expect(fileName).toMatch(/^runlog-测试应用-\d{8}-\d{6}\.txt$/)
    // 内容: 时间戳/中文级别/流程:行号/消息/错误堆栈
    expect(content).toContain('[')
    expect(content).toContain(' [信息] ')
    expect(content).toContain('[main:12] 流程开始')
    expect(content).toContain(' [错误] ')
    expect(content).toContain('[flow1:34] 执行失败')
    expect(content).toContain('Traceback (most recent call last):')
    expect(message.success).toHaveBeenCalled()
    expect(message.error).not.toHaveBeenCalled()
  })

  it('空日志: 提示无可导出日志, 不调用保存', async () => {
    getlogs.mockResolvedValue({ data: '[]' })
    const exportOpt = getMoreOpts().find(o => o.key === 'exportLog')!

    await exportOpt.clickFn(record)

    expect(utilsManager.saveFile).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith('noLogToExport')
  })

  it('res.data 为 undefined: 按 "[]" 兜底不抛异常', async () => {
    getlogs.mockResolvedValue({ data: undefined } as any)
    const exportOpt = getMoreOpts().find(o => o.key === 'exportLog')!

    await expect(exportOpt.clickFn(record)).resolves.toBeUndefined()
    expect(utilsManager.saveFile).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith('noLogToExport')
  })

  it('aPI 异常: 提示导出失败且异常不被抛出', async () => {
    getlogs.mockRejectedValue(new Error('network down'))
    const exportOpt = getMoreOpts().find(o => o.key === 'exportLog')!

    await expect(exportOpt.clickFn(record)).resolves.toBeUndefined()
    expect(utilsManager.saveFile).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith('exportLogFailed')
  })

  it('未知日志级别: 原样输出级别文本', async () => {
    getlogs.mockResolvedValue({
      data: JSON.stringify([{ event_time: 1755396000, data: { log_level: 'fatal', msg_str: 'boom' } }]),
    })
    const exportOpt = getMoreOpts().find(o => o.key === 'exportLog')!

    await exportOpt.clickFn(record)

    const [, content] = (utilsManager.saveFile as any).mock.calls[0]
    expect(content).toContain(' [fatal] boom')
  })

  it('原有菜单项不受影响', () => {
    const opts = getMoreOpts()
    expect(opts.map(o => o.key)).toEqual(
      expect.arrayContaining(['runningLog', 'runningDataTable', 'runningVideo', 'delete']),
    )
    // 数据表格菜单保持 disableFn 行为
    const dataTable = opts.find(o => o.key === 'runningDataTable')!
    expect(dataTable.disableFn?.({ dataTablePath: '' })).toBe(true)
    expect(dataTable.disableFn?.({ dataTablePath: '/a.xlsx' })).toBe(false)
  })
})
