<script setup lang="ts">
import { useElementSize } from '@vueuse/core'
import { debounce } from 'lodash-es'
import { onMounted, toRaw, useTemplateRef, watch } from 'vue'

import { WINDOW_NAME } from '@/constants'
import { windowManager } from '@/platform'
import type { AnyObj } from '@/types/common'
import UserFormDialog from '@/views/Arrange/components/customDialog/components/userFormDialog.vue'
import type { DialogOption } from '@/views/Arrange/components/customDialog/types'

import { transformData } from './utils'

const userFormRef = useTemplateRef<HTMLDivElement>('userFormRef')
const useFormSize = useElementSize(userFormRef)

async function resizeWindow() {
  const userFormEl = userFormRef.value
  if (!userFormEl)
    return
  // 计算设置自定义对话框窗口高度，实现高度随动
  const { offsetWidth: bodyWidth } = document.body
  // 判断计算高度是否超过了所在屏幕高度
  const screenWorkArea = await windowManager.getScreenWorkArea()
  // scrollHeight 不受 max-height 上限影响，始终以内容自然高度计算，避免上限和自适应互相打架
  const contentEl = userFormEl.querySelector<HTMLElement>('.userform-content')
  const naturalTotal = contentEl
    ? userFormEl.offsetHeight - contentEl.offsetHeight + contentEl.scrollHeight
    : useFormSize.height.value
  const resHeight = Math.min(Math.ceil(naturalTotal), screenWorkArea.height)
  await windowManager.setWindowSize({ width: bodyWidth, height: resHeight })
  if (contentEl) {
    // 内容超高时启用内部滚动（body overflow:hidden 下窗口级滚动不可用），否则放开上限完整展示
    const chrome = naturalTotal - contentEl.scrollHeight
    const budget = Math.floor(resHeight - chrome)
    document.documentElement.style.setProperty(
      '--uf-content-max',
      contentEl.scrollHeight > budget ? String(Math.max(budget, 200)) + 'px' : 'none',
    )
  }
  await windowManager.showWindow()
}

const debouncedResize = debounce(() => resizeWindow(), 150)
// 校验报错/动态增删项会改变内容高度，需要二次调整窗口，否则超出部分不可见
watch(useFormSize.height, () => debouncedResize())

const targetInfo = new URL(location.href).searchParams
const windowOption = transformData(JSON.parse(targetInfo.get('option'))) as DialogOption
const replyBaseData = JSON.parse(targetInfo.get('reply') || '{}') ?? {}

onMounted(() => resizeWindow())

function handleClose() {
  windowManager.closeWindow()
}

function handleSave(data: AnyObj) {
  windowManager.emitTo({
    from: WINDOW_NAME.USERFORM,
    target: WINDOW_NAME.MAIN,
    type: 'userFormSave',
    data: { ...replyBaseData, data: toRaw(data) },
  })
}
</script>

<template>
  <div ref="userFormRef">
    <UserFormDialog draggable :option="windowOption" @close="handleClose" @save="handleSave" />
  </div>
</template>
