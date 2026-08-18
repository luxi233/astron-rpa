<script setup lang="ts">
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { computed } from 'vue'

import { useFlowStore } from '@/stores/useFlowStore'
import { useProcessStore } from '@/stores/useProcessStore'

import AtomConfig from './AtomConfig.vue'

const { formItem } = defineProps<{ formItem: RPA.AtomDisplayItem }>()

const flowStore = useFlowStore()
const processStore = useProcessStore()

// 操作符选项由 meta 的 conditions 参数 options 提供(18种)
const condOptions = computed(() => formItem.options ?? [])

// 从当前节点 inputList 收集 args1_N/condition_N/args2_N 三元组(数量不限, 兼容旧流程已有行)
const rows = computed(() => {
  const list = flowStore.activeAtom?.inputList ?? []
  const nums = new Set<number>()
  for (const item of list) {
    const m = /^args1_(\d+)$/.exec(item.key)
    if (m)
      nums.add(Number(m[1]))
  }
  return [...nums].sort((a, b) => a - b).map(n => ({
    n,
    args1: list.find(i => i.key === `args1_${n}`),
    cond: list.find(i => i.key === `condition_${n}`),
    args2: list.find(i => i.key === `args2_${n}`),
  })).filter(row => row.args1)
})

function persist() {
  const atom = flowStore.activeAtom
  if (!atom)
    return
  const idx = flowStore.simpleFlowUIData.findIndex(item => item.id === atom.id)
  if (idx < 0)
    return
  flowStore.updataOriginFlowData([{ node: flowStore.simpleFlowUIData[idx], index: idx, process: processStore.activeProcessId }])
}

function nextRowNum() {
  return rows.value.length ? Math.max(...rows.value.map(r => r.n)) + 1 : 1
}

function addRow() {
  const atom = flowStore.activeAtom
  if (!atom)
    return
  const n = nextRowNum()
  atom.inputList.push(
    { types: 'Any', formType: { type: 'INPUT_VARIABLE_PYTHON' }, key: `args1_${n}`, name: `args1_${n}`, title: `对象1(条件${n})`, value: [{ type: 'other', value: '' }] },
    { types: 'Str', formType: { type: 'SELECT' }, key: `condition_${n}`, name: `condition_${n}`, title: `关系(条件${n})`, options: condOptions.value, value: condOptions.value[0]?.value ?? '==' },
    { types: 'Any', formType: { type: 'INPUT_VARIABLE_PYTHON' }, key: `args2_${n}`, name: `args2_${n}`, title: `对象2(条件${n})`, value: [{ type: 'other', value: '' }] },
  )
  persist()
}

function removeRow(n: number) {
  const atom = flowStore.activeAtom
  if (!atom || rows.value.length <= 1)
    return
  const keys = new Set([`args1_${n}`, `condition_${n}`, `args2_${n}`])
  const list = atom.inputList
  for (let i = list.length - 1; i >= 0; i--) {
    if (keys.has(list[i].key))
      list.splice(i, 1)
  }
  persist()
}

function onCondChange(item: RPA.AtomDisplayItem | undefined, val: string) {
  if (!item)
    return
  item.value = val
  flowStore.setFormItemValue(item.key, val, flowStore.activeAtom?.id)
}
</script>

<template>
  <div class="multi-condition w-full">
    <div
      v-for="row in rows"
      :key="row.n"
      class="cond-row flex items-center gap-1 mb-2"
    >
      <AtomConfig :form-item="row.args1" size="small" class="flex-1 min-w-0" />
      <a-select
        :value="row.cond?.value"
        :options="condOptions"
        size="small"
        class="cond-select shrink-0"
        :dropdown-match-select-width="false"
        @change="(val: any) => onCondChange(row.cond, val)"
      />
      <AtomConfig :form-item="row.args2" size="small" class="flex-1 min-w-0" />
      <DeleteOutlined
        v-if="rows.length > 1"
        class="shrink-0 cursor-pointer text-[rgba(0,0,0,0.45)] hover:text-error"
        @click="removeRow(row.n)"
      />
    </div>
    <a-button type="dashed" size="small" block @click="addRow">
      <template #icon>
        <PlusOutlined />
      </template>
      {{ $t('atomForm.addCondition') }}
    </a-button>
  </div>
</template>

<style lang="scss" scoped>
.multi-condition {
  .cond-select {
    width: 108px;
  }
}
</style>
