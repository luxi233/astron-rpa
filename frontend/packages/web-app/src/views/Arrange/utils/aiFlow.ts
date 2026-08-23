import { apiChatPrompt } from '@/api/aiCapability'
import { LIMIT_VARIABLE_SELECT, OTHER_IN_TYPE } from '@/constants/atom'

/** 原子清单条数与标题长度上限, 控制 prompt 体积 */
const MAX_ATOMS = 300
const TITLE_MAX_LEN = 30
/** 参数 schema 中每个参数最多展示的选项数 */
const MAX_OPTIONS = 8

export interface AiFlowStep {
  key: string
  reason: string
  /** AI 第二阶段填写的参数值(仅含可自动填写的表单项), 插入节点时回填 */
  params?: Record<string, any>
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

// ---------- 第二阶段: 参数自动填写 ----------

/** 可自动填值的表单类型分类; null = 不可自动填写(元素拾取/变量引用/文件等) */
type ParamKind = 'text' | 'select' | 'multi-select' | 'switch' | 'checkbox-group'

function paramKind(item: any): ParamKind | null {
  const type = String(item?.formType?.type ?? '')
  const typeArr = type.split('_')
  // 变量选择型参数(Browser/ExcelObj 等句柄)取值是变量引用, 不填字面值
  if (LIMIT_VARIABLE_SELECT.includes(item?.types))
    return null
  if (typeArr.includes('INPUT') || ['TEXTAREAMODAL', 'KEYBOARD', 'DATETIME', 'DEFAULTDATEPICKER', 'RANGEDATEPICKER'].includes(type))
    return 'text'
  if (type === 'SELECT' || type === 'RADIO')
    return item?.formType?.params?.multiple ? 'multi-select' : 'select'
  if (type === 'CHECKBOXGROUP')
    return 'checkbox-group'
  if (type === 'SWITCH' || type === 'CHECKBOX')
    return 'switch'
  return null
}

/** 静态选项对(仅保留有 label 的可枚举选项; 无 label 选项是变量式构造, 不可枚举) */
function optionPairs(item: any): Array<[string, string]> {
  return (item?.options || [])
    .filter((o: any) => o?.label != null)
    .map((o: any) => [String(o.value), String(o.label)])
}

/**
 * 构建步骤参数 schema 文本(与 flow_fill_params prompt 约定一致):
 * 每步 "序号. key|标题", 参数行 "   参数key=名称(类型[, 选项: 值:标签|...])", 纯函数便于单测。
 */
export function buildStepParamList(steps: AiFlowStep[], abilities: Record<string, any>): string {
  const lines: string[] = []
  steps.forEach((step, idx) => {
    const ability = abilities[step.key]
    lines.push(`${idx + 1}. ${step.key}|${ability?.title || step.key}`)
    const inputs: any[] = (ability?.inputList || []).filter((i: any) => i.level !== 'advanced')
    for (const item of inputs) {
      if (!paramKind(item))
        continue
      let desc = `${item.key}=${item.title || item.name || ''}(${String(item.formType?.type ?? '')}`
      const options = optionPairs(item)
      if (options.length) {
        const shown = options.slice(0, MAX_OPTIONS).map(([v, l]) => `${v}:${l}`).join('|')
        desc += `, 选项: ${shown}${options.length > MAX_OPTIONS ? '|...' : ''}`
      }
      lines.push(`   ${desc})`)
    }
  })
  return lines.join('\n')
}

/** 从 LLM 输出容错解析参数填写结果: [{index(1起), params}], 丢弃非法项(纯函数便于单测) */
export function parseAiParams(content: string | null | undefined): Array<{ index: number, params: Record<string, any> }> {
  if (typeof content !== 'string' || !content.trim())
    return []
  const match = content.match(/\{[\s\S]*\}/)
  if (!match)
    return []
  try {
    const data = JSON.parse(match[0])
    const steps = Array.isArray(data?.steps) ? data.steps : []
    return steps
      .map((s: any) => ({
        index: Number(s?.index),
        params: (s?.params && typeof s.params === 'object' && !Array.isArray(s.params)) ? s.params : {},
      }))
      .filter((s: any) => Number.isInteger(s.index) && s.index >= 1 && Object.keys(s.params).length > 0)
  }
  catch {
    return []
  }
}

/**
 * AI 填写流程参数(第二阶段): 需求 + 已编排步骤的参数 schema → 各步骤参数值。
 * 返回携带 params 的新步骤数组; 无可填参数/解析失败/接口异常返回 null(调用方降级为仅插骨架)。
 */
export async function aiFillFlowParams(description: string, steps: AiFlowStep[], abilities: Record<string, any>): Promise<AiFlowStep[] | null> {
  if (!steps.length)
    return null
  const schema = buildStepParamList(steps, abilities)
  // 所有步骤均无可自动填写参数(纯元素拾取等)时跳过第二次调用
  if (!schema.split('\n').some(line => line.startsWith('   ')))
    return null
  try {
    const res = await apiChatPrompt('flow_fill_params', { description, steps: schema })
    const fills = parseAiParams(res.data)
    if (!fills.length)
      return null
    const merged = steps.map(s => ({ ...s }))
    for (const fill of fills) {
      const step = merged[fill.index - 1]
      if (step)
        step.params = { ...(step.params || {}), ...fill.params }
    }
    return merged.some(s => s.params && Object.keys(s.params).length > 0) ? merged : null
  }
  catch (e) {
    console.error('ai fill flow params failed', e)
    return null
  }
}

/** 选项匹配: 先按值匹配, 再按标签匹配; 均未命中返回 undefined(非法选项丢弃) */
function matchOption(item: any, raw: any): string | undefined {
  const pairs = optionPairs(item)
  if (!pairs.length)
    return undefined
  const s = String(raw)
  const byValue = pairs.find(([v]) => v === s)
  if (byValue)
    return byValue[0]
  const byLabel = pairs.find(([, l]) => l === s)
  return byLabel ? byLabel[0] : undefined
}

/** 按表单类型把 LLM 字面值转成节点的 value 结构; 无法安全转换返回 undefined */
function shapeParamValue(item: any, kind: ParamKind, raw: any): any {
  switch (kind) {
    case 'text':
      return [{ type: OTHER_IN_TYPE, value: String(raw) }]
    case 'select': {
      const hit = matchOption(item, raw)
      return hit === undefined ? undefined : hit
    }
    case 'multi-select':
    case 'checkbox-group': {
      const arr = Array.isArray(raw) ? raw : [raw]
      const hits = arr.map(v => matchOption(item, v)).filter(v => v !== undefined)
      return hits.length ? hits : undefined
    }
    case 'switch':
      if (typeof raw === 'boolean')
        return raw
      if (raw === 'true')
        return true
      if (raw === 'false')
        return false
      return undefined
  }
  return undefined
}

/**
 * 把 AI 填写的参数回填到已插入的流程节点 inputList(原地修改 item.value), 返回成功回填数。
 * 非法参数 key/非法选项值/不可自动填写类型(元素拾取等)全部静默跳过, 纯函数便于单测。
 */
export function applyStepParams(node: any, params: Record<string, any> | undefined): number {
  if (!node?.inputList || !params)
    return 0
  let applied = 0
  for (const item of node.inputList) {
    const raw = params[item.key]
    if (raw === undefined || raw === null || raw === '')
      continue
    const kind = paramKind(item)
    if (!kind)
      continue
    const value = shapeParamValue(item, kind, raw)
    if (value === undefined)
      continue
    item.value = value
    applied++
  }
  return applied
}
