<script lang="ts" setup>
import type { ICellValue, ISheetWorkbookData, Sheet as SheetComponent, SheetLocaleType } from '@rpa/components'
import { Sheet, useTheme } from '@rpa/components'
import { useTranslation } from 'i18next-vue'
import { computed, shallowRef } from 'vue'

interface ItemConfig {
  bind: string
  defaultValue?: any
  [key: string]: any
}

const props = defineProps<{
  item: ItemConfig
  modelObj: Record<string, any>
}>()

type SheetType = InstanceType<typeof SheetComponent>

const { isDark } = useTheme()
const { i18next } = useTranslation()

const sheetRef = shallowRef<SheetType>()
const importing = shallowRef(false)

const locale = computed(() => {
  return (i18next.language === 'zh-CN' ? 'zhCN' : 'enUS') as SheetLocaleType
})

// 保证 modelObj[bind] 始终是可变二维数组（与表格内容保持同步）
if (!Array.isArray(props.modelObj[props.item.bind])) {
  props.modelObj[props.item.bind] = []
}

function ensureSize(rows: any[][], maxRow: number, maxCol: number) {
  while (rows.length <= maxRow) rows.push([])
  const row = rows[maxRow]
  while (row.length <= maxCol) row.push(null)
}

/** cellUpdate 增量同步到 modelObj（value 为原始标量或 null） */
function handleCellUpdate(cells: ICellValue[]) {
  const rows: any[][] = props.modelObj[props.item.bind]
  cells.forEach((it) => {
    ensureSize(rows, it.row, it.column)
    rows[it.row][it.column] = it.value == null ? null : it.value
  })
}

/** 二维数组转 Univer 工作簿数据 */
function transformToWorkbookData(rows: any[][]): Partial<ISheetWorkbookData> {
  const cellData: Record<number, Record<number, { v: any }>> = {}
  for (let row = 0; row < rows.length; row++) {
    const rowArray = rows[row] || []
    for (let col = 0; col < rowArray.length; col++) {
      const value = rowArray[col]
      if (value == null)
        continue
      if (!cellData[row])
        cellData[row] = {}
      cellData[row][col] = { v: value }
    }
  }
  return {
    appVersion: '',
    id: Date.now().toString(),
    locale: 'zhCN' as SheetLocaleType,
    name: 'datatable.xlsx',
    resources: [],
    sheetOrder: ['sheet'],
    sheets: {
      sheet: {
        id: 'sheet',
        cellData,
      },
    },
  }
}

/** Univer 工作簿快照转二维数组 */
function workbookToRows(workbookData: ISheetWorkbookData): any[][] {
  const sheetId = workbookData.sheetOrder?.[0]
  const cellData = (sheetId && workbookData.sheets?.[sheetId]?.cellData) || {}
  let maxRow = -1
  let maxCol = -1
  Object.keys(cellData).forEach((r) => {
    Object.keys(cellData[+r]).forEach((c) => {
      if (cellData[+r][+c]?.v != null) {
        maxRow = Math.max(maxRow, +r)
        maxCol = Math.max(maxCol, +c)
      }
    })
  })
  const rows: any[][] = []
  for (let r = 0; r <= maxRow; r++) {
    const row: any[] = []
    for (let c = 0; c <= maxCol; c++) row.push(cellData[r]?.[c]?.v ?? null)
    rows.push(row)
  }
  return rows
}

const defaultValue = computed(() => transformToWorkbookData(props.item.defaultValue || []))

/** 导入 Excel：解析后用第一个 sheet 替换整个表格 */
async function handleImport() {
  if (importing.value || !sheetRef.value)
    return
  importing.value = true
  try {
    const workbookData = await sheetRef.value.utils.importExcelFile()
    if (!workbookData)
      return
    const sheetId = workbookData.sheetOrder?.[0]
    if (!sheetId)
      return
    sheetRef.value.createWorkbook({
      ...workbookData,
      sheets: { [sheetId]: workbookData.sheets[sheetId] },
      sheetOrder: [sheetId],
    })
    props.modelObj[props.item.bind] = workbookToRows(workbookData)
  }
  finally {
    importing.value = false
  }
}
</script>

<template>
  <div class="datatable-form-item">
    <div class="datatable-toolbar">
      <a-button size="small" :loading="importing" @click="handleImport">
        {{ $t('common.import') }}Excel
      </a-button>
    </div>
    <div class="datatable-sheet">
      <Sheet
        ref="sheetRef"
        :dark-mode="isDark"
        :locale="locale"
        :default-value="defaultValue"
        @cell-update="handleCellUpdate"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.datatable-form-item {
  width: 100%;

  .datatable-toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 6px;
  }

  .datatable-sheet {
    height: 420px;
  }
}
</style>
