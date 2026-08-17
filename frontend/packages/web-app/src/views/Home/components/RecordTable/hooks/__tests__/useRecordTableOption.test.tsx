import { describe, expect, it, vi } from 'vitest'

vi.mock('i18next-vue', () => ({
  useTranslation: () => ({ t: (k: string) => k, i18next: { language: 'zh-CN' } }),
}))

vi.mock('@/views/Home/components/RecordTable/hooks/useRecordTableColumns.tsx', () => ({
  default: () => ({ columns: [{ key: 'oper' }] }),
}))

vi.mock('@/views/Home/components/RecordTable/hooks/useRecordOperation.tsx', () => ({
  default: () => ({
    rowSelection: {},
    getTableData: vi.fn(),
    batchDelete: vi.fn(),
  }),
}))

const useRecordTableOption = (await import('../useRecordTableOption.tsx')).default

describe('useRecordTableOption - 触发方式筛选表单', () => {
  it('主页(无 robotId): 表单含 4 项且 triggerType 选项正确', () => {
    const { tableOption } = useRecordTableOption({ robotId: '' })

    expect(tableOption.formList).toHaveLength(4)
    const binds = tableOption.formList.map((f: any) => f.bind)
    expect(binds).toEqual(['robotName', 'timeRange', 'result', 'triggerType'])

    const trigger = tableOption.formList.find((f: any) => f.bind === 'triggerType') as any
    expect(trigger.componentType).toBe('select')
    expect(trigger.placeholder).toBe('record.selectTriggerType')
    expect(trigger.isTrim).toBe(true)
    // 全部('') / 手动(manual) / 计划任务(task)
    expect(trigger.options).toEqual([
      { label: 'record.allTriggerType', value: '' },
      { label: 'record.manualRun', value: 'manual' },
      { label: 'record.taskRun', value: 'task' },
    ])

    // 原有执行结果筛选不受影响
    const result = tableOption.formList.find((f: any) => f.bind === 'result') as any
    expect(result.options.map((o: any) => o.value)).toEqual(['', 'robotSuccess', 'robotFail', 'robotCancel', 'robotExecute'])
  })

  it('应用详情页(带 robotId): 无筛选表单且 params 绑定 robotId', () => {
    const { tableOption } = useRecordTableOption({ robotId: 'rb-123' })

    expect(tableOption.formList).toEqual([])
    expect(tableOption.params.robotId).toBe('rb-123')
  })

  it('默认 params: robotName/robotId 为空字符串', () => {
    const { tableOption } = useRecordTableOption({ robotId: '' })
    expect(tableOption.params).toEqual({ robotName: '', robotId: '' })
  })
})
