<script lang="ts" setup>
import { AimOutlined, CloseOutlined, RedoOutlined } from '@ant-design/icons-vue'
import { NiceModal } from '@rpa/components'
import { Empty, message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { h, onMounted, onUnmounted, ref } from 'vue'

import { useElementsStore } from '@/stores/useElementsStore'
import { usePickStore } from '@/stores/usePickStore'

import { ElementPickModal } from './index'

// 后端 CONTROL_TREE 导出的节点结构(picker/core/control_tree.py)
interface ControlTreeNode {
  tag_name: string | null
  cls: string | null
  name: string | null
  automation_id: string | null
  rect: { left: number, top: number, right: number, bottom: number } | null
  children: ControlTreeNode[]
}

const modal = NiceModal.useModal()
const elementPickModal = NiceModal.useModal(ElementPickModal)
const usePick = usePickStore()
const useElements = useElementsStore()
const { t } = useTranslation()

const treeData = ref<any[]>([])
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])
const pickedNode = ref<any>(null) // 当前选中节点(含 raw), 供拾取使用
const picking = ref(false)
const fieldNames = { children: 'children', title: 'title', key: 'key' }

/**
 * 后端树 → antd 树数据, key 用路径索引保证唯一
 */
function convertNode(node: ControlTreeNode, key: string): any {
  return {
    key,
    title: node.tag_name || 'Control',
    isLeaf: !node.children || node.children.length === 0,
    raw: node,
    children: (node.children || []).map((child, idx) => convertNode(child, `${key}-${idx}`)),
  }
}

/**
 * 加载控件树
 */
function loadTree() {
  treeData.value = []
  expandedKeys.value = []
  selectedKeys.value = []
  usePick.openControlTree((res) => {
    if (res.success && res.data) {
      treeData.value = [convertNode(res.data, '0')]
      expandedKeys.value = ['0'] // 默认展开根节点
    }
  })
}

/**
 * 点选节点 → 桌面高亮对应控件区域
 */
function handleSelect(keys: any[], info: any) {
  if (!keys.length) {
    pickedNode.value = null
    return
  }
  selectedKeys.value = keys
  pickedNode.value = info?.node?.dataRef || null
  const raw: ControlTreeNode | undefined = info?.node?.dataRef?.raw
  if (raw?.rect) {
    usePick.highlightTreeNode(raw.rect)
  }
  else {
    message.info(t('controlTreeNoRect'))
  }
}

/**
 * 根据节点 key('0-1-2' 路径索引)回溯窗口层→目标层的属性链
 * 第 0 层为桌面根控件, 不构成元素路径, 需跳过
 */
function buildPickChain(nodeKey: string): ControlTreeNode[] {
  const indexes = nodeKey.split('-').map(Number)
  const chain: ControlTreeNode[] = []
  let nodes = treeData.value
  let current: any = null
  for (const idx of indexes) {
    current = nodes[idx]
    if (!current)
      return []
    chain.push(current.raw)
    nodes = current.children || []
  }
  return chain.slice(1) // 跳过桌面根层
}

/**
 * 拾取选中节点: 后端按属性链构造 UIA 元素并验证定位, 成功后进入元素保存弹窗
 */
function handlePickNode() {
  if (!pickedNode.value)
    return
  const chain = buildPickChain(pickedNode.value.key)
  if (!chain.length) {
    message.warning(t('controlTreePickInvalid'))
    return
  }
  picking.value = true
  usePick.pickTreeNode(chain, (res) => {
    picking.value = false
    if (!res.success)
      return
    const { element, located } = res.data || {}
    if (!located)
      message.warning(t('controlTreePickUnlocated'), 6)
    // 接入拾取保存链路: 临时元素 + 元素详情弹窗
    useElements.setTempElement({ ...element, img: { self: '', parent: '' } })
    modal.hide()
    elementPickModal.show()
  })
}

/**
 * 关闭弹窗并释放通道
 */
function handleClose() {
  modal.hide()
}

onMounted(() => {
  loadTree()
})

onUnmounted(() => {
  usePick.closeControlTree()
})
</script>

<template>
  <a-modal
    v-bind="NiceModal.antdModal(modal)"
    destroy-on-close
    centered
    :width="520"
    :z-index="20"
    :title="$t('controlTree')"
    class="controlTreeModal"
    :keyboard="false"
    :mask-closable="false"
    :footer="null"
  >
    <template #closeIcon>
      <CloseOutlined @click.stop="handleClose" />
    </template>
    <div class="control-tree-toolbar flex items-center justify-between mb-2">
      <span class="tip font-size-12">{{ $t('controlTreeTip') }}</span>
      <div>
        <a-button
          size="small"
          type="primary"
          :icon="h(AimOutlined)"
          :loading="picking"
          :disabled="!pickedNode"
          class="font-size-12 inline-flex-center mr-2"
          @click="handlePickNode"
        >
          {{ $t('controlTreePick') }}
        </a-button>
        <a-button
          size="small"
          :icon="h(RedoOutlined)"
          :loading="usePick.isTreeLoading"
          class="font-size-12 inline-flex-center"
          @click="loadTree"
        >
          {{ $t('refresh') }}
        </a-button>
      </div>
    </div>
    <div class="control-tree-wrapper border border-border">
      <a-spin :spinning="usePick.isTreeLoading">
        <a-tree
          v-if="treeData.length"
          v-model:expanded-keys="expandedKeys"
          v-model:selected-keys="selectedKeys"
          class="w-full control-tree"
          :tree-data="treeData"
          :field-names="fieldNames"
          :block-node="true"
          :open-animation="null"
          @select="handleSelect"
        >
          <template #title="{ data }">
            <span class="font-size-12">
              <span class="node-tag">{{ data.raw.tag_name || 'Control' }}</span>
              <span v-if="data.raw.name" class="node-name">"{{ data.raw.name }}"</span>
              <span v-if="data.raw.automation_id" class="node-attr">[{{ data.raw.automation_id }}]</span>
              <span v-if="data.raw.cls" class="node-attr">{{ data.raw.cls }}</span>
            </span>
          </template>
        </a-tree>
        <a-empty
          v-else-if="!usePick.isTreeLoading"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          :description="$t('noData')"
        />
      </a-spin>
    </div>
  </a-modal>
</template>

<style scoped lang="scss">
.font-size-12 {
  font-size: 12px;
}
.inline-flex-center {
  display: inline-flex;
  align-items: center;
}

.control-tree-toolbar .tip {
  color: rgb(0 0 0 / 45%);
}

.control-tree-wrapper {
  height: 420px;
  overflow-y: auto;
  padding: 4px;
}

.control-tree-wrapper::-webkit-scrollbar {
  width: 6px;
  background-color: #f5f5f5;
}

.control-tree-wrapper::-webkit-scrollbar-thumb {
  background-color: #cecece;
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
</style>
