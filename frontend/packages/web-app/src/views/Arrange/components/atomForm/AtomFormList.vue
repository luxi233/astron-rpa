<script setup lang="ts">
import { computed } from 'vue'

import AtomFormItem from './AtomFormItem.vue'

const { atomForm } = defineProps({
  atomForm: {
    type: Array<RPA.AtomDisplayItem>,
    default: () => ([]),
  },
})

const atomFormItem = computed(() => {
  // 多条件组件(MULTICONDITION)内部已渲染 args1_N/condition_N/args2_N 行, 存在该组件时过滤掉独立行避免重复渲染
  const hasMultiCondition = atomForm.some(item => item.formType?.type === 'MULTICONDITION')
  return atomForm.filter((item) => {
    if (hasMultiCondition && /^(args1|condition|args2)_\d+$/.test(item.key))
      return false
    return !item.dynamics || [undefined, true].includes(item.show)
  })
})
</script>

<template>
  <AtomFormItem v-for="atom in atomFormItem" :key="atom.key" :atom-form-item="atom" />
</template>
