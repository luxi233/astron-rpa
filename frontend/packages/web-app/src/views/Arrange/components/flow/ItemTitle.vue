<script setup lang="ts">
import { computed } from 'vue'

import { Group, GroupEnd, Note } from '@/views/Arrange/config/atomKeyMap'

const { item } = defineProps<{ item: RPA.Atom }>()

const iconName = computed(() => {
  switch (item.key) {
    case Group:
      return 'group-start'
    case GroupEnd:
      return 'group-end'
    case Note:
      return 'note'
    default:
      return item.icon
  }
})

const noteText = computed(() => {
  const noteValue = item.value && (item.value as Record<string, unknown>).note
  return (typeof noteValue === 'string' && noteValue.trim()) ? noteValue : (item.alias || item.title)
})
</script>

<template>
  <div class="inline font-medium">
    <rpa-hint-icon
      v-if="item.key !== Note"
      :name="iconName"
      class="inline-block mr-1 text-[#000000]/[.65] dark:text-[#FFFFFF]/[.65] relative top-[2px]"
    />
    <span v-if="item.key === Group || item.key === GroupEnd">
      <span class="text-primary">{{ item.alias || item.title }}</span>
      <template v-if="item.key === Group"> {{ $t('groupStart') }}</template>
      <template v-else> {{ $t('groupEnd') }}</template>
    </span>
    <span v-else-if="item.key === Note">
      <span class="italic text-[#000000]/[.45] dark:text-[#FFFFFF]/[.45]">// {{ noteText }}</span>
    </span>
    <span v-else>{{ item.alias || item.title }}</span>
  </div>
</template>
