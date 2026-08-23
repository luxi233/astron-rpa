<script lang="ts" setup>
import { LockOutlined } from '@ant-design/icons-vue'
import { computed, ref, watch } from 'vue'

import { usePickStore } from '@/stores/usePickStore'

// 引擎 dump_live_tree 导出的实时树节点(picker/core/control_tree.py), 比 ControlTreeNode 多 id/focused/root
interface LiveTreeNode {
  id: string
  tag_name: string | null
  cls: string | null
  name: string | null
  automation_id: string | null
  rect: { left: number, top: number, right: number, bottom: number } | null
  focused: boolean
  root?: boolean
  truncated?: boolean
  children: LiveTreeNode[]
}

// 优先用外部传入的树数据(独立面板窗口经 w2w 转发), 未传时回退读全局 store(主窗口内联场景);
// pickable 开启树节点双击捕获(双击节点标题即按祖先属性链完成拾取);
// frozen 为树固定状态(Ctrl+点击 toggle): 切换提示文案与状态图标;
// nodeProps 为引擎查询的选中节点 UIA 属性(主窗口经 w2w 回传), null 时回退节点自带字段
const props = defineProps<{
  treeData?: any
  pickable?: boolean
  frozen?: boolean
  nodeProps?: Record<string, any> | null
}>()
const emit = defineEmits<{
  (e: 'pick-node', chain: LiveTreeNode[]): void
  (e: 'select-node', chain: LiveTreeNode[]): void
}>()
const usePick = usePickStore()
const fieldNames = { children: 'children', title: 'title', key: 'key' }

const sourceTreeData = computed(() => props.treeData !== undefined ? props.treeData : usePick.liveTreeData)

const treeData = ref<any[]>([])
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])

// 右栏属性面板: 选中节点与其展示属性(引擎完整 UIA 属性未返回前先展示节点自带字段兜底)
const selectedRaw = ref<LiveTreeNode | null>(null)
const displayProps = ref<Record<string, string>>({})

/**
 * 实时树 → antd 树数据; 顺带收集祖先链 key 供自动展开到聚焦节点,
 * 并为每个节点附带祖先属性链 chain(顶层窗口层→自身, 供点选捕获/属性查询上报;
 * 桌面根节点不参与定位链, 与 CONTROL_TREE/TREE_PICK 的窗口层→目标层语义一致)
 */
function convertNode(node: LiveTreeNode, key: string, ancestry: string[], chain: LiveTreeNode[], focusedKeys: string[], focusedKey: { value: string }, isRoot = false) {
  if (node.focused) {
    focusedKey.value = key
    focusedKeys.push(...ancestry, key)
  }
  const nodeChain = isRoot ? [] : [...chain, node]
  return {
    key,
    title: node.tag_name || 'Control',
    isLeaf: !node.children || node.children.length === 0,
    raw: node,
    chain: nodeChain,
    children: (node.children || []).map((child, idx) => convertNode(child, `${key}-${idx}`, [...ancestry, key], nodeChain, focusedKeys, focusedKey)),
  }
}

// 每帧推送到达后重建树并自动展开/选中聚焦节点(引擎已做指纹去重+节流, 此处直接替换即可);
// 树结构已变化, 选中节点的属性随旧树失效, 一并清空
watch(sourceTreeData, (raw) => {
  selectedRaw.value = null
  displayProps.value = {}
  clearSelectTimer()
  if (!raw) {
    treeData.value = []
    return
  }
  const focusedKeys: string[] = []
  const focusedKey = { value: '' }
  treeData.value = [convertNode(raw, '0', [], [], focusedKeys, focusedKey, true)]
  expandedKeys.value = focusedKeys.length ? focusedKeys : ['0']
  selectedKeys.value = focusedKey.value ? [focusedKey.value] : []
})

// 引擎属性查询结果到达后替换兜底字段(null=定位失败, 保持节点自带字段)
watch(() => props.nodeProps, (v) => {
  if (v && Object.keys(v).length)
    displayProps.value = v
})

// 单击节点的属性查询延迟派发: 双击(捕获)时取消挂起的查询, 避免 2 次属性查询 + 1 次捕获的串行定位
let selectTimer: ReturnType<typeof setTimeout> | null = null
function clearSelectTimer() {
  if (selectTimer) {
    clearTimeout(selectTimer)
    selectTimer = null
  }
}

// 单击节点: 选中并展示属性(先渲染节点自带字段兜底, 再异步上报主窗口查询完整 UIA 属性)
function handleSelectNode(data: any) {
  selectedRaw.value = data.raw as LiveTreeNode
  selectedKeys.value = [data.key]
  const fallback: Record<string, string> = {}
  if (data.raw.tag_name)
    fallback.ControlTypeName = data.raw.tag_name
  if (data.raw.name)
    fallback.Name = data.raw.name
  if (data.raw.cls)
    fallback.ClassName = data.raw.cls
  if (data.raw.automation_id)
    fallback.AutomationId = data.raw.automation_id
  if (data.raw.rect) {
    const r = data.raw.rect
    fallback.BoundingRectangle = `(${r.left}, ${r.top}) - (${r.right}, ${r.bottom})`
  }
  displayProps.value = fallback
  clearSelectTimer()
  selectTimer = setTimeout(() => {
    selectTimer = null
    emit('select-node', data.chain)
  }, 220)
}

// 双击节点: 完成捕获前先取消挂起的属性查询(引擎定位为秒级同步调用, 串行叠加拖慢捕获)
function handlePickNode(data: any) {
  clearSelectTimer()
  emit('pick-node', data.chain)
}

const focusedRaw = computed<LiveTreeNode | null>(() => {
  const find = (nodes: any[]): LiveTreeNode | null => {
    for (const n of nodes) {
      if (n.raw?.focused)
        return n.raw
      const hit = find(n.children || [])
      if (hit)
        return hit
    }
    return null
  }
  return find(treeData.value)
})
</script>

<template>
  <div class="live-tree-panel flex h-full">
    <div class="tree-col flex flex-col flex-1 min-w-0">
      <div class="live-tree-header">
        <div class="live-tree-title flex items-center">
          <LockOutlined v-if="props.frozen" class="frozen-icon" />
          <span v-else class="live-dot" />
          {{ $t('deepCaptureLiveTree') }}
        </div>
        <div class="live-tree-tip">
          {{ props.frozen ? $t('deepCaptureTreeFrozenTip') : $t('deepCaptureLiveTreeTip') }}
        </div>
      </div>
      <div class="live-tree-body flex-1">
        <a-tree
          v-if="treeData.length"
          v-model:expanded-keys="expandedKeys"
          v-model:selected-keys="selectedKeys"
          class="w-full live-tree"
          :tree-data="treeData"
          :field-names="fieldNames"
          :block-node="true"
          :selectable="false"
          :open-animation="null"
        >
          <template #title="{ data }">
            <span
              class="font-size-12"
              :class="{ 'focused-node': data.raw.focused, 'pickable-node': props.pickable }"
              @click="handleSelectNode(data)"
              @dblclick="props.pickable && handlePickNode(data)"
            >
              <span class="node-tag">{{ data.raw.tag_name || 'Control' }}</span>
              <span v-if="data.raw.name" class="node-name">"{{ data.raw.name }}"</span>
              <span v-if="data.raw.automation_id" class="node-attr">[{{ data.raw.automation_id }}]</span>
            </span>
          </template>
        </a-tree>
        <div v-else class="live-tree-placeholder">
          {{ $t('deepCaptureLiveTreeWaiting') }}
        </div>
      </div>
      <div v-if="focusedRaw?.rect" class="live-tree-footer">
        {{ focusedRaw.rect.right - focusedRaw.rect.left }} × {{ focusedRaw.rect.bottom - focusedRaw.rect.top }}
      </div>
    </div>
    <div class="props-col flex flex-col">
      <div class="props-title">
        {{ $t('deepCapturePropsTitle') }}
      </div>
      <div class="props-body flex-1">
        <div v-if="!selectedRaw" class="props-empty">
          {{ $t('deepCapturePropsEmpty') }}
        </div>
        <table v-else class="props-table">
          <tbody>
            <tr v-for="(val, key) in displayProps" :key="key">
              <td class="props-key">
                {{ key }}
              </td>
              <td class="props-val" :title="val">
                {{ val }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.live-tree-panel {
  background: #fff;
  border-left: 1px solid #e8e8e8;
}

.live-tree-header {
  padding: 8px 12px 6px;
  border-bottom: 1px solid #f0f0f0;
}

.live-tree-title {
  font-size: 13px;
  font-weight: 600;
}

.live-dot {
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 50%;
  background: #52c41a;
  animation: live-blink 1.2s infinite;
}

@keyframes live-blink {
  50% {
    opacity: 0.35;
  }
}

.frozen-icon {
  margin-right: 6px;
  font-size: 12px;
  color: #1677ff;
}

.live-tree-tip {
  margin-top: 2px;
  font-size: 12px;
  color: rgb(0 0 0 / 45%);
}

.live-tree-body {
  padding: 4px;
  overflow-y: auto;
}

.live-tree-body::-webkit-scrollbar {
  width: 6px;
  background-color: #f5f5f5;
}

.live-tree-body::-webkit-scrollbar-thumb {
  background-color: #cecece;
}

.live-tree-placeholder {
  padding: 24px 12px;
  font-size: 12px;
  color: rgb(0 0 0 / 45%);
  text-align: center;
}

.live-tree-footer {
  padding: 4px 12px;
  font-size: 12px;
  color: rgb(0 0 0 / 45%);
  border-top: 1px solid #f0f0f0;
}

.node-tag {
  font-weight: 500;
}

.node-name {
  margin-left: 4px;
}

.node-attr {
  margin-left: 4px;
  color: rgb(0 0 0 / 45%);
}

.focused-node {
  color: #1677ff;

  .node-tag {
    font-weight: 600;
  }
}

.pickable-node {
  display: inline-block;
  width: 100%;
  cursor: pointer;

  &:hover {
    color: #1677ff;
  }
}

// 右栏属性面板(影刀式双栏: 左树右属性)
.props-col {
  width: 264px;
  flex-shrink: 0;
  border-left: 1px solid #e8e8e8;
}

.props-title {
  padding: 8px 12px 6px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid #f0f0f0;
}

.props-body {
  padding: 4px 8px;
  overflow-y: auto;
}

.props-body::-webkit-scrollbar {
  width: 6px;
  background-color: #f5f5f5;
}

.props-body::-webkit-scrollbar-thumb {
  background-color: #cecece;
}

.props-empty {
  padding: 24px 12px;
  font-size: 12px;
  color: rgb(0 0 0 / 45%);
  text-align: center;
}

.props-table {
  width: 100%;
  font-size: 12px;
  border-collapse: collapse;
  table-layout: fixed;

  tr {
    border-bottom: 1px solid #f5f5f5;
  }

  td {
    padding: 4px 6px;
    vertical-align: top;
    word-break: break-all;
  }
}

.props-key {
  width: 92px;
  color: rgb(0 0 0 / 45%);
}

.props-val {
  color: rgb(0 0 0 / 85%);
}
</style>
