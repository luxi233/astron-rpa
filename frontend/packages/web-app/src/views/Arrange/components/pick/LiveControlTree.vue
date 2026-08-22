<script lang="ts" setup>
import { computed, ref, watch } from 'vue'

import { usePickStore } from '@/stores/usePickStore'

// 引擎 dump_live_tree 导出的实时树节点(picker/core/control_tree.py), 比 ControlTreeNode 多 id/focused
interface LiveTreeNode {
  id: string
  tag_name: string | null
  cls: string | null
  name: string | null
  automation_id: string | null
  rect: { left: number, top: number, right: number, bottom: number } | null
  focused: boolean
  truncated?: boolean
  children: LiveTreeNode[]
}

// 优先用外部传入的树数据(独立面板窗口经 w2w 转发), 未传时回退读全局 store(主窗口内联场景);
// pickable 开启树节点点选捕获(点击节点标题即按祖先属性链完成拾取)
const props = defineProps<{
  treeData?: any
  pickable?: boolean
}>()
const emit = defineEmits<{
  (e: 'pick-node', chain: LiveTreeNode[]): void
}>()
const usePick = usePickStore()
const fieldNames = { children: 'children', title: 'title', key: 'key' }

const sourceTreeData = computed(() => props.treeData !== undefined ? props.treeData : usePick.liveTreeData)

const treeData = ref<any[]>([])
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])

/**
 * 实时树 → antd 树数据; 顺带收集祖先链 key 供自动展开到聚焦节点,
 * 并为每个节点附带祖先属性链 chain(窗口层→自身, 供点选捕获上报)
 */
function convertNode(node: LiveTreeNode, key: string, ancestry: string[], chain: LiveTreeNode[], focusedKeys: string[], focusedKey: { value: string }) {
  if (node.focused) {
    focusedKey.value = key
    focusedKeys.push(...ancestry, key)
  }
  const nodeChain = [...chain, node]
  return {
    key,
    title: node.tag_name || 'Control',
    isLeaf: !node.children || node.children.length === 0,
    raw: node,
    chain: nodeChain,
    children: (node.children || []).map((child, idx) => convertNode(child, `${key}-${idx}`, [...ancestry, key], nodeChain, focusedKeys, focusedKey)),
  }
}

// 每帧推送到达后重建树并自动展开/选中聚焦节点(引擎已做指纹去重+节流, 此处直接替换即可)
watch(sourceTreeData, (raw) => {
  if (!raw) {
    treeData.value = []
    return
  }
  const focusedKeys: string[] = []
  const focusedKey = { value: '' }
  treeData.value = [convertNode(raw, '0', [], [], focusedKeys, focusedKey)]
  expandedKeys.value = focusedKeys.length ? focusedKeys : ['0']
  selectedKeys.value = focusedKey.value ? [focusedKey.value] : []
})

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
  <div class="live-tree-panel flex flex-col h-full">
    <div class="live-tree-header">
      <div class="live-tree-title flex items-center">
        <span class="live-dot" />
        {{ $t('deepCaptureLiveTree') }}
      </div>
      <div class="live-tree-tip">
        {{ $t('deepCaptureLiveTreeTip') }}
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
            @click="props.pickable && emit('pick-node', data.chain)"
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
</style>
