/**
 * AI 能力前端纯函数与 API 封装单元测试
 *
 * 覆盖 C14/C15 新增链路:
 * T1. aiSetting API 封装(GET/PUT/POST 走 /api/rpa-ai-service/admin/ai-config*)
 * T2. apiChatPrompt 封装(prompt_type/params/stream 载荷)
 * T3. buildTreeSummary 树摘要(序号/截断/key 映射/节点数上限) 与 parseAiNodes 容错解析
 * T4. buildAtomList 原子清单摘要 与 parseAiSteps 容错解析
 * T5. aiGenerateFlow 步骤过滤(LLM 编造 key 丢弃)/失败返回 null
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
const { buildAtomList, parseAiSteps, aiGenerateFlow } = await import('@/views/Arrange/utils/aiFlow')

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
