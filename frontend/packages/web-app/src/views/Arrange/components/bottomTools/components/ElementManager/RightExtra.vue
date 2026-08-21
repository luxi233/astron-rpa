<script lang="ts" setup>
import { throttle } from 'lodash-es'
import { computed } from 'vue'

import { useCvPickStore } from '@/stores/useCvPickStore'
import { usePickStore } from '@/stores/usePickStore'
import { useCvPick } from '@/views/Arrange/components/cvPick/hooks/useCvPick'

import ElementManageHeader from '../ElementManageHeader.vue'

import ElementBtns from './ElementBtns.vue'

const usePick = usePickStore()
const cvPickStore = useCvPickStore()
const { pick: cvPick } = useCvPick()

// 捕获模式(对齐影刀三模式): 标准-默认/深度/CV图像
const picking = computed(() => usePick.isPicking || cvPickStore.isPicking)

// 拾取新元素(按捕获模式分发)
const pickNewElement = throttle((key: string) => {
  if (key === 'deep') {
    // 深度捕获: 跳过策略试探, UIA 更大深度下钻
    usePick.newDeepPick()
  }
  else if (key === 'cv') {
    // CV捕获: 走独立 vision-picker 图像框选链路
    cvPick()
  }
  else {
    // 标准捕获(默认): 网页走DOM/桌面走UIA+MSAA择优
    usePick.newPick('')
  }
}, 1000, { leading: true, trailing: false })
</script>

<template>
  <ElementManageHeader :placeholder="$t('searchElements')">
    <template #btns>
      <a-dropdown placement="bottomRight" :trigger="['click']" :disabled="picking">
        <template #overlay>
          <a-menu class="w-[240px] !bg-white dark:!bg-[#1F1F1F]" mode="vertical" @click="({ key }) => pickNewElement(key as string)">
            <a-menu-item key="standard">
              <div class="pick-mode-label">
                {{ $t('pickModeStandard') }}
              </div>
              <div class="pick-mode-tip">
                {{ $t('pickModeStandardTip') }}
              </div>
            </a-menu-item>
            <a-menu-item key="deep">
              <div class="pick-mode-label">
                {{ $t('pickModeDeep') }}
              </div>
              <div class="pick-mode-tip">
                {{ $t('pickModeDeepTip') }}
              </div>
            </a-menu-item>
            <a-menu-item key="cv">
              <div class="pick-mode-label">
                {{ $t('pickModeCv') }}
              </div>
              <div class="pick-mode-tip">
                {{ $t('pickModeCvTip') }}
              </div>
            </a-menu-item>
          </a-menu>
        </template>
        <ElementBtns :loading="picking" :disabled="picking" />
      </a-dropdown>
    </template>
  </ElementManageHeader>
</template>

<style lang="scss" scoped>
.pick-mode-label {
  font-size: 12px;
  line-height: 20px;
}

.pick-mode-tip {
  font-size: 11px;
  line-height: 16px;
  color: #999;
  white-space: normal;
}
</style>
