/**
 * 数据表格前端数据流单元测试
 *
 * 覆盖 useRunningStore 中数据表格的前后端一致性链路:
 * T1. SSE file_changed → fetchDataTable → dataTable 更新为 active sheet
 * T2. SSE file_deleted → dataTable 置空
 * T3. reset() 关闭监听前兜底拉取一次最终数据(修复: 清空后落盘事件晚于流程结束时不残留旧数据)
 * T4. updateDataTableCell 本地乐观更新 + max_row/max_column 收敛(区域外 null 不扩容)
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRunningStore } from '@/stores/useRunningStore'

const mockStartDataTableListener = vi.fn()
const mockGetDataTable = vi.fn()
const mockCloseDataTable = vi.fn()
const mockUpdateDataTable = vi.fn()
const mockStartExecutor = vi.fn()
const mockStopExecutor = vi.fn()
const mockDeleteDataTable = vi.fn()

vi.mock('@/api/resource', () => ({
  startDataTableListener: (...args: any[]) => mockStartDataTableListener(...args),
  getDataTable: (...args: any[]) => mockGetDataTable(...args),
  closeDataTable: (...args: any[]) => mockCloseDataTable(...args),
  updateDataTable: (...args: any[]) => mockUpdateDataTable(...args),
  deleteDataTable: (...args: any[]) => mockDeleteDataTable(...args),
  startExecutor: (...args: any[]) => mockStartExecutor(...args),
  stopExecutor: (...args: any[]) => mockStopExecutor(...args),
}))

vi.mock('@/api/ws', () => ({
  default: class MockSocket {
    OPTIONS: any = { reconnectCount: 5 }
    bindMessage() {}
    bindOpen() {}
    bindClose() {}
    create() {}
    isConnect() { return true }
    destroy() {}
    send() {}
  },
}))

vi.mock('@/platform', () => ({
  windowManager: { minimizeWindow: vi.fn(), maximizeWindow: vi.fn() },
}))

vi.mock('@/plugins/i18next', () => ({ default: { t: (k: string) => k } }))

vi.mock('@/utils/common', () => ({
  generateUUID: () => 'test-uuid',
  getCookie: () => '',
  sleep: () => Promise.resolve(),
}))

vi.mock('@/utils/env', () => ({ baseUrl: 'http://test' }))
vi.mock('@/constants', () => ({ WINDOW_NAME: { USERFORM: 'userform' } }))
vi.mock('@/views/Arrange/components/flow/hooks/useChangeStatus', () => ({ changeDebugging: vi.fn() }))
vi.mock('ant-design-vue', () => ({
  message: { warning: vi.fn() },
  notification: { close: vi.fn(), open: vi.fn(), info: vi.fn(), warning: vi.fn(), error: vi.fn() },
  Progress: { name: 'Progress', props: {} },
}))

vi.mock('@/stores/useProcessStore', () => ({
  useProcessStore: () => ({ project: { id: 'p1' }, isComponent: false }),
}))
vi.mock('@/stores/useFlowStore', () => ({ useFlowStore: () => ({}) }))
vi.mock('@/stores/useRunlogStore', () => ({ useRunlogStore: () => ({ clearLogs: vi.fn(), addLog: vi.fn() }) }))
vi.mock('@/stores/useUserSetting.ts', () => ({ default: () => ({ userSetting: { videoForm: {} } }) }))

describe('useRunningStore 数据表格数据流', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStartExecutor.mockResolvedValue({})
  })

  it('t1: file_changed 事件触发 fetchDataTable, dataTable 更新为 active sheet', async () => {
    let sseCallback: ((res: any) => void) | undefined
    mockStartDataTableListener.mockImplementation((_id, cb) => {
      sseCallback = cb
      return { abort: vi.fn() }
    })
    mockGetDataTable.mockResolvedValue({
      active_sheet: 'Sheet1',
      sheets: [
        { name: 'Sheet1', data: [['a', 'b'], ['c', null]], max_row: 2, max_column: 2 },
        { name: 'Other', data: [['x']], max_row: 1, max_column: 1 },
      ],
    })

    const store = useRunningStore()
    store.startRun('p1', 'proc1') // start() → _startDataTableListener()
    await new Promise(r => setTimeout(r, 0))

    expect(mockStartDataTableListener).toHaveBeenCalledWith('p1', expect.any(Function))
    expect(sseCallback).toBeTypeOf('function')

    sseCallback!({ event: 'file_changed' })
    await new Promise(r => setTimeout(r, 0))

    // 拉取的是当前项目, dataTable 取 active_sheet 对应的 sheet(而非第一个)
    expect(mockGetDataTable).toHaveBeenCalledWith('p1')
    expect(store.dataTable).toMatchObject({ name: 'Sheet1', max_row: 2 })
    expect((store.dataTable as any).data[0]).toEqual(['a', 'b'])
  })

  it('t2: file_deleted 事件将 dataTable 置空', async () => {
    let sseCallback: ((res: any) => void) | undefined
    mockStartDataTableListener.mockImplementation((_id, cb) => {
      sseCallback = cb
      return { abort: vi.fn() }
    })

    const store = useRunningStore()
    store.startRun('p1', 'proc1')
    await new Promise(r => setTimeout(r, 0))

    sseCallback!({ event: 'file_deleted' })
    await new Promise(r => setTimeout(r, 0))

    expect(store.dataTable).toBeNull()
    // file_deleted 不触发拉取
    expect(mockGetDataTable).not.toHaveBeenCalled()
  })

  it('t3: reset() 关闭监听前兜底拉取最终数据并 abort/close', async () => {
    const abort = vi.fn()
    mockStartDataTableListener.mockImplementation(() => ({ abort }))
    mockGetDataTable.mockResolvedValue({
      active_sheet: 'Sheet1',
      sheets: [{ name: 'Sheet1', data: [], max_row: 0, max_column: 0 }],
    })

    const store = useRunningStore()
    store.startRun('p1', 'proc1')
    await new Promise(r => setTimeout(r, 0))

    const callsBeforeReset = mockGetDataTable.mock.calls.length
    store.reset()
    await new Promise(r => setTimeout(r, 0))

    // 兜底拉取: reset 期间至少多一次 getDataTable
    expect(mockGetDataTable.mock.calls.length).toBeGreaterThan(callsBeforeReset)
    // 关闭监听
    expect(abort).toHaveBeenCalled()
    expect(mockCloseDataTable).toHaveBeenCalledWith('p1')
    // 兜底拉取失败(fetchDataTable reject)不应导致 reset 抛错
    mockGetDataTable.mockRejectedValueOnce(new Error('network'))
    expect(() => store.reset()).not.toThrow()
  })

  it('t4: updateDataTableCell 乐观更新本地数据并收敛边界(区域外 null 不扩容)', async () => {
    mockUpdateDataTable.mockResolvedValue({})
    const store = useRunningStore()
    // @ts-expect-error 测试直接注入表格状态
    store.dataTable = {
      name: 'Sheet1',
      data: [['a', 'b'], [null, 'd']],
      max_row: 2,
      max_column: 2,
    }

    // 区域内清空 (row:1, col:1) → data[1][1]=null
    await store.updateDataTableCell([{ row: 1, col: 1, value: null }])
    expect(mockUpdateDataTable).toHaveBeenCalledWith('p1', [{ sheet: 'Sheet1', row: 1, col: 1, value: null }])
    const table: any = store.dataTable
    expect(table.data[1][1]).toBeNull()
    // 行1 全空后边界收敛: 只剩行0 → max_row=1, 行0 最后非空列是 b(col1) → max_column=2
    expect(table.max_row).toBe(1)
    expect(table.max_column).toBe(2)

    // 区域外 null 写入: 不落 API 也不污染本地边界
    const calls = mockUpdateDataTable.mock.calls.length
    await store.updateDataTableCell([{ row: 9, col: 0, value: null }])
    expect(mockUpdateDataTable.mock.calls.length).toBe(calls + 1)
    expect(table.max_row).toBe(1)
    expect(table.max_column).toBe(2)
    expect(table.data[9]).toBeUndefined()
  })
})
