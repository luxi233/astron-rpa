/**
 * AI 能力前端纯函数与 API 封装单元测试
 *
 * 覆盖 C14/C15 新增链路:
 * T1. aiSetting API 封装(GET/PUT/POST 走 /api/rpa-ai-service/admin/ai-config*)
 * T2. apiChatPrompt 封装(prompt_type/params/stream 载荷)
 * T3. buildTreeSummary 树摘要(序号/截断/key 映射/节点数上限) 与 parseAiNodes 容错解析
 * T4. buildAtomList 原子清单摘要 与 parseAiSteps 容错解析
 * T5. aiGenerateFlow 步骤过滤(LLM 编造 key 丢弃)/失败返回 null
 * T6. buildStepParamList 参数 schema(可填类型过滤/选项枚举/截断)
 * T7. parseAiParams 容错解析(非法 index/空 params 丢弃)
 * T8. applyStepParams 参数回填(INPUT 数组结构/SELECT 选项匹配/不可填类型跳过)
 * T9. aiFillFlowParams 第二阶段合并/降级语义
 */
import { describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()

vi.mock('@/api/http', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
  },
}))

const { apiGetAIConfig, apiSaveAIConfig, apiTestAIConfig } = await import('@/api/aiSetting')
const { apiChatPrompt } = await import('@/api/aiCapability')
const { buildTreeSummary, parseAiNodes } = await import('@/views/DeepPick/aiSearch')
const { buildAtomList, parseAiSteps, aiGenerateFlow, buildStepParamList, parseAiParams, applyStepParams, aiFillFlowParams } = await import('@/views/Arrange/utils/aiFlow')

describe('t1. aiSetting API 封装', () => {
  it('apiGetAIConfig 走 GET /admin/ai-config', () => {
    mockGet.mockReturnValueOnce(Promise.resolve({ data: {} }))
    apiGetAIConfig()
    expect(mockGet).toHaveBeenCalledWith('/api/rpa-ai-service/admin/ai-config')
  })

  it('apiSaveAIConfig 走 PUT 并携带 values 载荷', () => {
    mockPut.mockReturnValueOnce(Promise.resolve({ data: {} }))
    apiSaveAIConfig({ DEFAULT_MODEL: 'maas/deepseek-v3.2' })
    expect(mockPut).toHaveBeenCalledWith('/api/rpa-ai-service/admin/ai-config', {
      values: { DEFAULT_MODEL: 'maas/deepseek-v3.2' },
    })
  })

  it('apiTestAIConfig 走 POST /admin/ai-config/test', () => {
    mockPost.mockReturnValueOnce(Promise.resolve({ data: {} }))
    apiTestAIConfig()
    expect(mockPost).toHaveBeenCalledWith('/api/rpa-ai-service/admin/ai-config/test', {})
  })
})

describe('t2. apiChatPrompt 封装', () => {
  it('pOST /v1/chat/prompt 携带 prompt_type/params/stream', () => {
    mockPost.mockReturnValueOnce(Promise.resolve({ data: '{}' }))
    apiChatPrompt('element_search', { query: '登录按钮', tree: '1. Button' })
    expect(mockPost).toHaveBeenCalledWith('/api/rpa-ai-service/v1/chat/prompt', {
      prompt_type: 'element_search',
      params: { query: '登录按钮', tree: '1. Button' },
      stream: false,
    })
  })
})

describe('t3. DeepPick 树摘要与节点解析', () => {
  const root = {
    tag_name: 'Desktop',
    children: [
      {
        tag_name: 'WindowControl',
        name: '主窗口',
        children: [
          { tag_name: 'ButtonControl', name: '登录', children: [] },
          { tag_name: 'EditControl', name: null, automation_id: 'user_input', children: [] },
        ],
      },
    ],
  }

  it('buildTreeSummary 生成带序号摘要并映射到路径键(根不编号)', () => {
    const { summary, keyByIndex } = buildTreeSummary(root as any)
    const lines = summary.split('\n')
    expect(lines).toHaveLength(3)
    expect(lines[0]).toBe('1. WindowControl "主窗口"')
    expect(lines[1]).toBe('2. ButtonControl "登录"')
    expect(lines[2]).toBe('3. EditControl [user_input]')
    // 序号 → '0-1-2' 路径键(与 LiveControlTree convertNode 一致)
    expect(keyByIndex['1']).toBe('0-0')
    expect(keyByIndex['2']).toBe('0-0-0')
    expect(keyByIndex['3']).toBe('0-0-1')
  })

  it('buildTreeSummary 空树/超长 name 截断', () => {
    expect(buildTreeSummary(null).summary).toBe('')
    const longName = { tag_name: 'TextControl', name: 'x'.repeat(60), children: [] }
    const { summary } = buildTreeSummary({ children: [longName] } as any)
    expect(summary).toContain('...')
    // name 截断为 40 字符 + 省略号, 不包含 41 个连续 x
    expect(summary).not.toContain('x'.repeat(41))
  })

  it('parseAiNodes 容错提取 nodes 序号(代码块/噪音/非法输入)', () => {
    expect(parseAiNodes('```json\n{"nodes": ["2", "3"]}\n```')).toEqual(['2', '3'])
    expect(parseAiNodes('结果如下 {"nodes": ["1"]} 请查收')).toEqual(['1'])
    expect(parseAiNodes('{"nodes": []}')).toEqual([])
    expect(parseAiNodes('{"nodes": ["abc", 5]}')).toEqual(['5'])
    expect(parseAiNodes('not json')).toEqual([])
    expect(parseAiNodes(null)).toEqual([])
  })
})

describe('t4. Arrange 原子清单与步骤解析', () => {
  it('buildAtomList 每行 key|标题 并截断超长标题', () => {
    const list = buildAtomList([
      { key: 'web_open', title: '打开网页' },
      { key: 'excel_write', title: 'x'.repeat(50) },
    ])
    const lines = list.split('\n')
    expect(lines[0]).toBe('web_open|打开网页')
    expect(lines[1]).toContain('...')
    expect(lines[1].length).toBeLessThan(50)
  })

  it('parseAiSteps 容错提取 steps(丢弃缺 key 项)', () => {
    expect(parseAiSteps('```json\n{"steps": [{"key": "a", "reason": "打开"}]}\n```'))
      .toEqual([{ key: 'a', reason: '打开' }])
    expect(parseAiSteps('{"steps": [{"reason": "无key"}, {"key": "b"}]}'))
      .toEqual([{ key: 'b', reason: '' }])
    expect(parseAiSteps('{"steps": []}')).toEqual([])
    expect(parseAiSteps('bad')).toEqual([])
    expect(parseAiSteps(undefined)).toEqual([])
  })
})

describe('t5. aiGenerateFlow 过滤与失败语义', () => {
  const atoms = [
    { key: 'web_open', title: '打开网页' },
    { key: 'web_click', title: '点击元素' },
  ]

  it('过滤清单外的编造 key', async () => {
    mockPost.mockReturnValueOnce(Promise.resolve({
      data: '{"steps": [{"key": "web_open", "reason": "a"}, {"key": "hack_key", "reason": "b"}, {"key": "web_click", "reason": "c"}]}',
    }))
    const steps = await aiGenerateFlow('打开并点击', atoms)
    expect(steps).toEqual([
      { key: 'web_open', reason: 'a' },
      { key: 'web_click', reason: 'c' },
    ])
  })

  it('全部被过滤/解析失败返回 null', async () => {
    mockPost.mockReturnValueOnce(Promise.resolve({ data: '{"steps": [{"key": "nope", "reason": "x"}]}' }))
    expect(await aiGenerateFlow('需求', atoms)).toBeNull()
    mockPost.mockReturnValueOnce(Promise.resolve({ data: 'not json' }))
    expect(await aiGenerateFlow('需求', atoms)).toBeNull()
  })

  it('接口异常返回 null(不向上抛)', async () => {
    mockPost.mockRejectedValueOnce(new Error('network'))
    expect(await aiGenerateFlow('需求', atoms)).toBeNull()
  })

  it('空原子清单直接返回 null(不发请求)', async () => {
    mockPost.mockClear()
    expect(await aiGenerateFlow('需求', [])).toBeNull()
    expect(mockPost).not.toHaveBeenCalled()
  })
})

describe('t6. buildStepParamList 参数 schema', () => {
  const steps = [{ key: 'web_open', reason: '打开' }]
  const abilities = {
    web_open: {
      title: '打开网页',
      inputList: [
        { key: 'url', title: '网址', types: 'Str', formType: { type: 'INPUT' } },
        { key: 'browser', title: '浏览器', types: 'Str', formType: { type: 'SELECT' }, options: [
          { label: 'Chrome', value: 'chrome' },
          { label: 'Edge', value: 'edge' },
        ] },
        // 以下三类不应出现在 schema 中
        { key: 'element', title: '目标元素', formType: { type: 'ELEMENT' } },
        { key: 'adv', title: '高级项', level: 'advanced', formType: { type: 'INPUT' } },
        { key: 'handle', title: '浏览器对象', types: 'Browser', formType: { type: 'INPUT_VARIABLE' } },
      ],
    },
  }

  it('只列可自动填写参数, 选项枚举为 值:标签', () => {
    const schema = buildStepParamList(steps, abilities)
    const lines = schema.split('\n')
    expect(lines[0]).toBe('1. web_open|打开网页')
    expect(lines[1]).toBe('   url=网址(INPUT)')
    expect(lines[2]).toBe('   browser=浏览器(SELECT, 选项: chrome:Chrome|edge:Edge)')
    expect(lines).toHaveLength(3)
  })

  it('原子能力缺失时仅输出步骤行(无参数行)', () => {
    const schema = buildStepParamList(steps, {})
    expect(schema).toBe('1. web_open|web_open')
  })
})

describe('t7. parseAiParams 容错解析', () => {
  it('提取 index/params 并丢弃非法项', () => {
    expect(parseAiParams('```json\n{"steps": [{"index": 1, "params": {"url": "https://baidu.com"}}]}\n```'))
      .toEqual([{ index: 1, params: { url: 'https://baidu.com' } }])
    expect(parseAiParams('{"steps": [{"index": 0, "params": {"a": 1}}, {"index": 2, "params": {}}, {"params": {"b": 2}}]}'))
      .toEqual([])
    expect(parseAiParams('not json')).toEqual([])
    expect(parseAiParams(null)).toEqual([])
  })
})

describe('t8. applyStepParams 参数回填', () => {
  const node = () => ({
    inputList: [
      { key: 'url', types: 'Str', formType: { type: 'INPUT' }, value: [{ type: 'other', value: '' }] },
      { key: 'browser', types: 'Str', formType: { type: 'SELECT' }, options: [
        { label: 'Chrome', value: 'chrome' },
        { label: 'Edge', value: 'edge' },
      ], value: '' },
      { key: 'headless', types: 'Bool', formType: { type: 'SWITCH' }, value: false },
      { key: 'element', formType: { type: 'ELEMENT' }, value: null },
    ],
  })

  it('iNPUT 回填为 [{type:other,value}] 结构', () => {
    const n = node()
    expect(applyStepParams(n, { url: 'https://www.baidu.com' })).toBe(1)
    expect(n.inputList[0].value).toEqual([{ type: 'other', value: 'https://www.baidu.com' }])
  })

  it('sELECT 按标签/值匹配选项, 非法选项与未知 key 跳过', () => {
    const n = node()
    expect(applyStepParams(n, { browser: 'Chrome', url: 'x', nope: 'y' })).toBe(2)
    expect(n.inputList[1].value).toBe('chrome')
    const n2 = node()
    expect(applyStepParams(n2, { browser: 'firefox' })).toBe(0)
    expect(n2.inputList[1].value).toBe('')
  })

  it('sWITCH 字符串布尔与不可填类型处理', () => {
    const n = node()
    expect(applyStepParams(n, { headless: 'true', element: 'fake' })).toBe(1)
    expect(n.inputList[2].value).toBe(true)
    expect(n.inputList[3].value).toBeNull()
    expect(applyStepParams(null, { a: 1 })).toBe(0)
    expect(applyStepParams(node(), undefined)).toBe(0)
  })
})

describe('t9. aiFillFlowParams 合并与降级', () => {
  const steps = [
    { key: 'web_open', reason: '打开' },
    { key: 'web_input', reason: '输入' },
  ]
  const abilities = {
    web_open: { title: '打开网页', inputList: [{ key: 'url', title: '网址', types: 'Str', formType: { type: 'INPUT' } }] },
    web_input: { title: '输入内容', inputList: [{ key: 'text', title: '内容', types: 'Str', formType: { type: 'INPUT' } }] },
  }

  it('按 index 合并 params 到步骤', async () => {
    mockPost.mockReturnValueOnce(Promise.resolve({
      data: '{"steps": [{"index": 1, "params": {"url": "https://www.baidu.com"}}, {"index": 9, "params": {"text": "编造"}}]}',
    }))
    const merged = await aiFillFlowParams('打开百度', steps, abilities)
    expect(merged).toEqual([
      { key: 'web_open', reason: '打开', params: { url: 'https://www.baidu.com' } },
      { key: 'web_input', reason: '输入' },
    ])
    expect(mockPost).toHaveBeenCalledWith('/api/rpa-ai-service/v1/chat/prompt', {
      prompt_type: 'flow_fill_params',
      params: { description: '打开百度', steps: expect.stringContaining('url=网址(INPUT)') },
      stream: false,
    })
  })

  it('解析失败/接口异常返回 null(降级为仅骨架)', async () => {
    mockPost.mockReturnValueOnce(Promise.resolve({ data: 'not json' }))
    expect(await aiFillFlowParams('需求', steps, abilities)).toBeNull()
    mockPost.mockRejectedValueOnce(new Error('network'))
    expect(await aiFillFlowParams('需求', steps, abilities)).toBeNull()
  })

  it('无可填参数时不发请求直接返回 null', async () => {
    mockPost.mockClear()
    const onlyPick = [{ key: 'web_click', reason: '点击' }]
    const pickOnly = { web_click: { title: '点击元素', inputList: [{ key: 'element', title: '目标元素', formType: { type: 'ELEMENT' } }] } }
    expect(await aiFillFlowParams('需求', onlyPick, pickOnly)).toBeNull()
    expect(mockPost).not.toHaveBeenCalled()
  })
})
