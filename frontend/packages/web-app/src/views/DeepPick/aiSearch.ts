import { apiChatPrompt } from '@/api/aiCapability'

/** 实时树节点(与 LiveControlTree 的 LiveTreeNode 同构, 此处独立声明避免环依赖) */
interface TreeNode {
  tag_name?: string | null
  name?: string | null
  cls?: string | null
  automation_id?: string | null
  children?: TreeNode[]
}

/** 摘要节点数与单节点 name 长度上限, 控制 prompt 体积 */
const MAX_NODES = 200
const NAME_MAX_LEN = 40

export interface TreeSummary {
  /** 多行文本摘要(每节点一行: 序号. tag "name" [automation_id]) */
  summary: string
  /** 序号(1-based) → 树节点 key(与 LiveControlTree convertNode 生成的 '0-1-2' 路径键一致) */
  keyByIndex: Record<string, string>
}

/** 深度优先展开实时树为带序号的文本摘要, 供 LLM 按序号定位节点(纯函数, 便于单测) */
export function buildTreeSummary(root: TreeNode | null | undefined): TreeSummary {
  const lines: string[] = []
  const keyByIndex: Record<string, string> = {}
  let count = 0

  const walk = (node: TreeNode, key: string) => {
    for (let idx = 0; idx < (node.children?.length ?? 0); idx++) {
      if (count >= MAX_NODES)
        return
      const child = node.children![idx]
      const childKey = `${key}-${idx}`
      count++
      keyByIndex[String(count)] = childKey
      let name = (child.name ?? '').trim()
      if (name.length > NAME_MAX_LEN)
        name = `${name.slice(0, NAME_MAX_LEN)}...`
      const parts = [`${count}. ${child.tag_name || 'Control'}`]
      if (name)
        parts.push(`"${name}"`)
      if (child.automation_id)
        parts.push(`[${child.automation_id}]`)
      lines.push(parts.join(' '))
      walk(child, childKey)
    }
  }

  if (root)
    walk(root, '0')

  return { summary: lines.join('\n'), keyByIndex }
}

/** 从 LLM 输出容错解析节点序号列表: 提取首个 JSON 对象的 nodes 数组(纯函数, 便于单测) */
export function parseAiNodes(content: string | null | undefined): string[] {
  if (typeof content !== 'string' || !content.trim())
    return []
  const match = content.match(/\{[\s\S]*\}/)
  if (!match)
    return []
  try {
    const data = JSON.parse(match[0])
    const nodes = Array.isArray(data?.nodes) ? data.nodes : []
    return nodes
      .map((n: unknown) => String(n))
      .filter(n => /^\d+$/.test(n))
  }
  catch {
    return []
  }
}

/**
 * AI 查找元素: 自然语言 → 树摘要序号 → 树节点 key(供 LiveControlTree 选中展开)。
 * 找不到/接口异常返回 null(调用方保持现状不提示报错噪音)。
 */
export async function aiSearchElement(query: string, root: TreeNode | null | undefined): Promise<string | null> {
  const { summary, keyByIndex } = buildTreeSummary(root)
  if (!summary)
    return null
  try {
    const res = await apiChatPrompt('element_search', { query, tree: summary })
    const nodes = parseAiNodes(res.data)
    for (const node of nodes) {
      const key = keyByIndex[node]
      if (key)
        return key
    }
    return null
  }
  catch (e) {
    console.error('ai search element failed', e)
    return null
  }
}
