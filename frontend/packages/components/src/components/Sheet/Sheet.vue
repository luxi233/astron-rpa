<script lang="ts" setup>
import { theme } from 'ant-design-vue'
import { useTemplateRef, onBeforeUnmount, onMounted, watch } from 'vue'
import { twMerge } from 'tailwind-merge'
import { set } from 'lodash-es'
import { generate } from '@ant-design/colors';

import type { FUniver, Univer, IWorkbookData, CellValue, Theme } from '@univerjs/presets'
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core'
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN'
import UniverPresetSheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US'
import { createUniver, LocaleType, mergeLocales, defaultTheme, LogLevel } from '@univerjs/presets'
import { UniverSheetsFindReplacePreset } from '@univerjs/preset-sheets-find-replace'
import sheetsFindReplaceZhCN from '@univerjs/preset-sheets-find-replace/locales/zh-CN'
import sheetsFindReplaceEnUS from '@univerjs/preset-sheets-find-replace/locales/en-US'

import '@univerjs/preset-sheets-core/lib/index.css'
import '@univerjs/preset-sheets-find-replace/lib/index.css'

import { sheetUtils } from './utils'

interface SheetProps {
  darkMode?: boolean
  locale?: LocaleType
  readonly?: boolean
  class?: string
  defaultValue?: Partial<IWorkbookData>
}

export interface ICellValue {
  row: number
  column: number
  value: CellValue | null
}

// 真正改变单元格值的 mutation 白名单(SheetValueChanged 事件同时会被
// set-col-data 列宽/set-row-data 行高等纯样式 mutation 触发, 需过滤)
const VALUE_CHANGE_MUTATIONS = new Set([
  'sheet.mutation.set-range-values',
  'sheet.mutation.move-range',
  'sheet.mutation.remove-worksheet-merge',
  'sheet.mutation.add-worksheet-merge',
  'sheet.mutation.reorder-range',
])

const props = withDefaults(defineProps<SheetProps>(), {
  darkMode: false,
  locale: LocaleType.ZH_CN,
  defaultValue: () => ({})
})

const emits = defineEmits<{
  (e: 'ready'): void
  (e: 'rendered'): void
  (e: 'cellUpdate', data: ICellValue[]): void
}>()

const container = useTemplateRef<HTMLElement>('container')

const { token } = theme.useToken()

let univerInstance: Univer | null = null
let univerAPIInstance: FUniver | null = null

onMounted(() => {
  const colors = generate(token.value.colorPrimary);

  const themeToUse: Theme = {
    ...defaultTheme,
    primary: {
      50: colors[0],
      100: colors[1],
      200: colors[2],
      300: colors[3],
      400: colors[4],
      500: colors[5],
      600: colors[6],
      700: colors[7],
      800: colors[8],
      900: colors[9],
    }
  }

  const { univer, univerAPI } = createUniver({
    logLevel: LogLevel.WARN,
    theme: themeToUse,
    darkMode: props.darkMode,
    locale: props.locale,
    locales: {
      [LocaleType.ZH_CN]: mergeLocales(
        UniverPresetSheetsCoreZhCN,
        sheetsFindReplaceZhCN,
      ),
      [LocaleType.EN_US]: mergeLocales(
        UniverPresetSheetsCoreEnUS,
        sheetsFindReplaceEnUS,
      ),
    },
    presets: [
      UniverSheetsCorePreset({
        header: false,
        contextMenu: !props.readonly,
        footer: false,
        container: container.value as HTMLElement,
      }),
      UniverSheetsFindReplacePreset(),
    ],
  })

  // 添加生命周期监听事件
  univerAPI.addEvent(
    univerAPI.Event.LifeCycleChanged,
    ({ stage }) => {
      if (stage === univerAPI.Enum.LifecycleStages.Rendered) {
        emits('rendered')
        
        if (!props.readonly) return

        const fWorkbook = univerAPI.getActiveWorkbook()!
        const unitId = fWorkbook.getId()

        // disable selection
        fWorkbook.disableSelection()

        // set read only
        const permission = fWorkbook.getPermission()
        permission.setWorkbookEditPermission(unitId, false)
        permission.setPermissionDialogVisible(false)
      } else if (stage === univerAPI.Enum.LifecycleStages.Steady) {
        emits('ready')
      }
    },
  )

  univerAPI.createWorkbook(props.defaultValue)

  univerAPI.addEvent(univerAPI.Event.SheetValueChanged, (params) => {
    // 列宽/行高/默认样式等纯样式 mutation 也会触发该事件, 但并不改变单元格值,
    // 若不过滤会把整列(含大量 null 空行)回写, 导致数据表格数据被清空
    const mutationId: string | undefined = params.payload?.id
    if (mutationId && !VALUE_CHANGE_MUTATIONS.has(mutationId)) {
      return
    }

    const cellValues: ICellValue[] = params.effectedRanges.flatMap(it => {
      const { startRow, startColumn } = it.getRange();
      const values = it.getValues();
      
      // 将二维数组转换为 ICellValue 数组
      const result: ICellValue[] = []
      for (let i = 0; i < values.length; i++) {
        const row = startRow + i
        const rowValues = values[i] || []
        for (let j = 0; j < rowValues.length; j++) {
          const column = startColumn + j
          const cellValue = rowValues[j]
          result.push({
            row,
            column,
            value: cellValue == null ? null : cellValue as CellValue,
          })
        }
      }
      return result
    })
    
    emits('cellUpdate', cellValues)
  })

  univerInstance = univer
  univerAPIInstance = univerAPI
})

const getWorkbookData = () => {
  const fWorkbook = univerAPIInstance?.getActiveWorkbook()
  if (!fWorkbook) return
  return fWorkbook.save()
}

const createWorkbook = (workbookData: Partial<IWorkbookData>) => {
  univerAPIInstance?.createWorkbook(workbookData)
}

const updateCellValues = (values: ICellValue[]) => {
  const fWorkbook = univerAPIInstance?.getActiveWorkbook()
  const fWorksheet = fWorkbook?.getActiveSheet()
  const fRange = fWorksheet?.getRange('A1:B2')
  
  const cellValue: Record<number, Record<number, CellValue>> = {}
  values.forEach(it => {
    if (!cellValue[it.row]) {
      cellValue[it.row] = {}
    }
    set(cellValue, [it.row, it.column], it.value)
  });

  fRange?.setValues(cellValue)
}

onBeforeUnmount(() => {
  univerInstance?.dispose()
  univerAPIInstance?.dispose()
  univerInstance = null
  univerAPIInstance = null
})

watch(() => props.darkMode, (isDarkMode) => {
  univerAPIInstance?.toggleDarkMode(isDarkMode)
})

watch(() => props.locale, (locale) => {
  univerAPIInstance?.setLocale(locale)
})

defineExpose({
  utils: sheetUtils,
  getWorkbookData,
  createWorkbook,
  updateCellValues,
  undo: () => univerAPIInstance?.undo(),
  redo: () => univerAPIInstance?.redo(),
  // 打开查找替换弹窗
  openFindDialog: () => {
    univerAPIInstance?.executeCommand("ui.operation.open-find-dialog")
  },
  // 清空全部数据
  clearAll: () => createWorkbook({}),
  // 删除选中区域内容
  deleteSelection: () => {
    const fWorkbook = univerAPIInstance?.getActiveWorkbook()
    if (!fWorkbook) return

    const fWorksheet = fWorkbook.getActiveSheet()
    // 获取激活选区的范围
    const fSelection = fWorksheet.getSelection()
    const activeRange = fSelection?.getActiveRange()
    activeRange?.clear()
  },
})
</script>

<template>
  <div ref="container" :class="twMerge('h-full', props.class)" />
</template>
