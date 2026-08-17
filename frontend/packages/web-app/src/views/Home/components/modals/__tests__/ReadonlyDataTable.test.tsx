import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h } from 'vue'

// ---- mock 依赖 ----
// 注: 本套件不使用 @vue/test-utils——当前 vitest 3.2.6 环境下 VTU(vite-node 外部化加载)
// 与 SFC 组件会解析到两个 vue 实例导致响应式断链(mount 后永不重渲染),
// 改用与组件同一 vite ESM 管线的 createApp 手动挂载, 保证 vue 单实例。
const transformExcelToUniver = vi.fn(async (_file: File) => ({ id: 'wb-1', sheets: { sheet1: {} } }))

vi.mock('@rpa/components', async () => {
  const { defineComponent, h, ref } = await import('vue')
  return {
    // 轻量 stub: 把被断言的 props 序列化到 DOM, 规避 univerjs 真实加载
    Sheet: defineComponent({
      name: 'SheetStub',
      props: {
        defaultValue: { type: Object, default: null },
        readonly: { type: Boolean, default: false },
        darkMode: { type: Boolean, default: false },
        locale: { type: String, default: 'zhCN' },
      },
      setup(props) {
        return () => h('div', {
          'class': 'sheet-stub',
          'data-default': JSON.stringify(props.defaultValue),
          'data-readonly': String(props.readonly),
        })
      },
    }),
    sheetUtils: { transformExcelToUniver },
    useTheme: () => ({ isDark: ref(false) }),
  }
})

vi.mock('i18next-vue', () => ({
  useTranslation: () => ({ t: (k: string) => k, i18next: { language: 'zh-CN' } }),
}))

const fileRead = vi.fn()

vi.mock('@/api/resource', () => ({
  fileRead: (...args: any[]) => fileRead(...args),
}))

const blob2File = vi.fn((data: any, name: string) => new File(['raw'], name))

vi.mock('@/utils/common', () => ({
  blob2File,
}))

const AEmpty = defineComponent({
  name: 'AEmpty',
  props: ['description'],
  render() { return h('div', { class: 'empty-stub' }) },
})

const ReadonlyDataTable = (await import('../ReadonlyDataTable.vue')).default

/** 挂载到真实 document, 返回根元素 */
function mountComponent(props: Record<string, any>) {
  const el = document.createElement('div')
  document.body.appendChild(el)
  const app = createApp(ReadonlyDataTable, props)
  app.config.globalProperties.$t = ((k: string) => k) as any
  app.component('a-empty', AEmpty)
  app.mount(el)
  return { el, unmount: () => { app.unmount(); el.remove() } }
}

const tick = () => new Promise(r => setTimeout(r, 0))

describe('readonlyDataTable - 主页执行结果数据表格', () => {
  let cleanups: Array<() => void>

  beforeEach(() => {
    vi.clearAllMocks()
    transformExcelToUniver.mockResolvedValue({ id: 'wb-1', sheets: { sheet1: {} } })
    cleanups = []
    return () => cleanups.forEach(fn => fn())
  })

  it('挂载后: fileRead → blob2File → 模块级 sheetUtils 转换 → 渲染 Sheet', async () => {
    const blob = new Blob(['excel-bytes'])
    fileRead.mockResolvedValue({ data: blob })

    const { el, unmount } = mountComponent({ dataTablePath: '/data/table/xxx.xlsx' })
    cleanups.push(unmount)

    await tick()
    await tick()

    // 数据加载链路
    expect(fileRead).toHaveBeenCalledWith({ path: '/data/table/xxx.xlsx' })
    expect(blob2File).toHaveBeenCalledWith(blob, 'data-table.xlsx')
    // 核心回归: 转换使用模块级 sheetUtils, 不依赖 Sheet 组件实例(旧代码 sheetRef.value.utils 导致主页表格空白)
    expect(transformExcelToUniver).toHaveBeenCalledTimes(1)
    expect(transformExcelToUniver.mock.calls[0][0]).toBeInstanceOf(File)

    // Sheet 渲染并拿到转换结果
    const sheet = el.querySelector('.sheet-stub') as HTMLElement
    expect(sheet).not.toBeNull()
    expect(sheet.getAttribute('data-default')).toBe(JSON.stringify({ id: 'wb-1', sheets: { sheet1: {} } }))
    expect(sheet.getAttribute('data-readonly')).toBe('true')
    expect(el.querySelector('.empty-stub')).toBeNull()
  })

  it('加载中/失败: 显示占位而非崩溃', async () => {
    fileRead.mockRejectedValue(new Error('file not found'))

    const { el, unmount } = mountComponent({ dataTablePath: '/gone.xlsx' })
    cleanups.push(unmount)

    await tick()
    await tick()

    expect(transformExcelToUniver).not.toHaveBeenCalled()
    expect(el.querySelector('.sheet-stub')).toBeNull()
    expect(el.querySelector('.empty-stub')).not.toBeNull()
  })

  it('class 透传到 Sheet', async () => {
    fileRead.mockResolvedValue({ data: new Blob(['x']) })

    const { el, unmount } = mountComponent({ dataTablePath: '/a.xlsx', class: 'my-table' })
    cleanups.push(unmount)

    await tick()
    await tick()

    const sheet = el.querySelector('.sheet-stub') as HTMLElement
    expect(sheet).not.toBeNull()
    expect(sheet.classList.contains('my-table')).toBe(true)
  })
})
