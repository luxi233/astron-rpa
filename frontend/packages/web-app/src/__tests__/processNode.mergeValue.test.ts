/**
 * createSingleNode 保存值与原子 manifest 默认值合并的回归测试。
 *
 * 缺陷背景: 打开流程时节点保存值与原子能力默认值的合并曾使用 falsy 判断
 * (!findItem.value), 导致已保存的合法值 false / 0 被误判为"缺失"并被 manifest
 * 默认值覆盖。典型症状: "删除数据表格内容"原子取消"行移动"勾选(保存 false)后,
 * 重新进入流程又被自动勾上(默认 true)。
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createSingleNode } from '@/corobot/utils/processNode'

// 断循环依赖: processNode -> Arrange/utils -> contextMenu -> shortcuts -> contextMenu,
// shortcuts 在模块初始化时同步调用 getContextMenuList(), 测试环境需 mock
// (vi.mock 会被 vitest 提升到文件顶部, 放在 import 之后不影响生效)
vi.mock('@/views/Arrange/utils/contextMenu', () => ({
  getContextMenuList: () => [],
  toggleContextmenu: () => {},
  getSelected: () => [],
  setContextMenu: () => {},
  clickContextItem: () => {},
  getDisabled: () => false,
  getTitle: () => '',
  enableContextMenuKeyboard: () => {},
  disableContextMenuKeyboard: () => {},
}))

const ATOM_KEY = 'data_table.data_table.delete_data'

function makeAbility() {
  return {
    key: ATOM_KEY,
    inputList: [
      // 布尔勾选类参数, manifest 默认 true
      { key: 'delete_row_move', title: '行移动', default: true, formType: { type: 'CHECKBOX' }, types: 'Bool', required: false },
      // 数值类参数, manifest 默认 1
      { key: 'row', title: '行号', default: 1, formType: { type: 'INPUT' }, types: 'Int', required: false },
    ],
    outputList: [],
  }
}

function makeNode(inputList: any[]) {
  return {
    key: ATOM_KEY,
    version: '1.0.0',
    id: 'node_1',
    alias: '删除数据表格内容',
    inputList,
    outputList: [],
    advanced: [],
    exception: [],
  }
}

const astNode = { level: 0 }

describe('createSingleNode 打开流程时保存值回填', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('保存的布尔 false 被保留, 不被 manifest 默认 true 覆盖', () => {
    const node = makeNode([
      { key: 'delete_row_move', value: false },
      { key: 'row', value: [{ type: 'other', value: '2' }] },
    ])
    const vm = createSingleNode(node as any, astNode as any, makeAbility())
    expect(vm.inputList.find(i => i.key === 'delete_row_move')?.value).toBe(false)
  })

  it('保存的数值 0 被保留, 不被 manifest 默认值覆盖', () => {
    const node = makeNode([
      { key: 'row', value: 0 },
      { key: 'delete_row_move', value: true },
    ])
    const vm = createSingleNode(node as any, astNode as any, makeAbility())
    expect(vm.inputList.find(i => i.key === 'row')?.value).toBe(0)
  })

  it('保存值真正缺失(无该 key / value 为 null)时才回填 manifest 默认值', () => {
    const node = makeNode([{ key: 'row', value: null }])
    const vm = createSingleNode(node as any, astNode as any, makeAbility())
    expect(vm.inputList.find(i => i.key === 'delete_row_move')?.value).toBe(true)
    expect(vm.inputList.find(i => i.key === 'row')?.value).toBe(1)
  })
})
