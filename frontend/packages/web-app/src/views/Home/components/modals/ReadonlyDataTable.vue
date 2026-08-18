<script setup lang="ts">
import { Sheet, sheetUtils, useTheme } from '@rpa/components'
import type { ISheetWorkbookData, SheetLocaleType } from '@rpa/components'
import { useAsyncState } from '@vueuse/core'
import { useTranslation } from 'i18next-vue'
import { computed } from 'vue'

import { blob2File } from '@/utils/common'

import { fileRead } from '@/api/resource'

const props = defineProps<{ dataTablePath: string, class?: string }>()

const { isDark } = useTheme()
const { i18next } = useTranslation()

const { state: workbookData, error: loadError } = useAsyncState<ISheetWorkbookData>(async () => {
  const { data } = await fileRead({ path: props.dataTablePath })
  const file = blob2File(data, 'data-table.xlsx')
  return sheetUtils.transformExcelToUniver(file)
}, null)

const locale = computed<SheetLocaleType>(() => {
  return (i18next.language === 'zh-CN' ? 'zhCN' : 'enUS') as SheetLocaleType
})
</script>

<template>
  <Sheet
    v-if="workbookData"
    readonly
    :class="props.class"
    :default-value="workbookData"
    :dark-mode="isDark"
    :locale="locale"
  />
  <a-empty v-else-if="loadError" :description="$t('common.loadFailed')" />
  <a-empty v-else :description="$t('common.loading')" />
</template>
