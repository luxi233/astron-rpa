import { apiChatPrompt } from '@/api/aiCapability'

/** 原子清单条数与标题长度上限, 控制 prompt 体积 */
const MAX_ATOMS = 300
const TITLE_MAX_LEN = 30

export interface AiFlowStep {
  key: string
  reason: string
}

/** 原子能力清单摘要(每行 key|标题 截断, 与 flow_generate prompt 约定一致), 纯函数便于单测 */
export function buildAtomList(atoms: Array<{ key: string, title: string }>): string {
  return atoms
    .slice(0, MAX_ATOMS)
    .map((a) => {
      let title = (a.title || '').trim()
      if (title.length > TITLE_MAX_LEN)
        title = `${title.slice(0, TITLE_MAX_LEN)}...`
      return `${a.key}|${title}`
    })
    .join('\n')
}

/** 从 LLM 输出容错解析步骤列表: 提取首个 JSON 对象的 steps 数组(纯函数便于单测) */
export function parseAiSteps(content: string | null | undefined): AiFlowStep[] {
  if (typeof content !== 'string' || !content.trim())
    return []
  const match = content.match(/\{[\s\S]*\}/)
  if (!match)
    return []
  try {
    const data = JSON.parse(match[0])
    const steps = Array.isArray(data?.steps) ? data.steps : []
    return steps
      .map((s: any) => ({ key: String(s?.key ?? ''), reason: String(s?.reason ?? '') }))
      .filter(s => s.key)
  }
  catch {
    return []
  }
}

/**
 * AI 生成流程: 需求+原子清单 → 步骤列表(过滤清单外的 key, LLM 编造的丢弃)。
 * 解析失败/接口异常/无有效步骤返回 null(调用方提示失败)。
 */
export async function aiGenerateFlow(description: string, atoms: Array<{ key: string, title: string }>): Promise<AiFlowStep[] | null> {
  const atomList = buildAtomList(atoms)
  if (!atomList)
    return null
  try {
    const res = await apiChatPrompt('flow_generate', { description, atoms: atomList })
    const steps = parseAiSteps(res.data)
    if (!steps.length)
      return null
    const known = new Set(atoms.map(a => a.key))
    const filtered = steps.filter(s => known.has(s.key))
    return filtered.length ? filtered : null
  }
  catch (e) {
    console.error('ai generate flow failed', e)
    return null
  }
}
