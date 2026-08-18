<script setup lang="ts">
import { message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import type { Ref } from 'vue'
import { computed, inject, onMounted, ref, watch } from 'vue'

import BUS from '@/utils/eventBus'

import { getSmartComponentId, isSmartComponentKey } from '@/components/SmartComponent/utils'
import { SMARTCOMPONENT } from '@/constants/menu'
import { useRoutePush } from '@/hooks/useCommonRoute'
import { useFlowStore } from '@/stores/useFlowStore'
import { useProcessStore } from '@/stores/useProcessStore'
import { renderBaseConfig, useBaseConfig } from '@/views/Arrange/components/atomForm/hooks/useBaseConfig'
import type { AtomTabs } from '@/views/Arrange/types/atomForm'

import AtomFormList from './AtomFormList.vue'

const { i18next, t } = useTranslation()
const isShowFormItem = inject<Ref<boolean>>('showAtomFormItem', ref(true))

const activeKey = ref<number>(0)
const sidebarWide = ref(false)
const flowStore = useFlowStore()
const atomTab = ref<AtomTabs[]>([])
const formattedTabs = computed(() => {
  return atomTab.value.map((item, index) => ({
    title: item.name,
    value: index,
  }))
})

interface AtomGuide {
  title?: string
  steps?: string[]
  script?: string
}

// 解析原子组件 helpManual 中嵌入的设置指南（{"guide": {"title","steps","script"}}）
const atomGuide = computed<AtomGuide | null>(() => {
  const raw = flowStore.activeAtom?.helpManual
  if (!raw)
    return null
  try {
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    const guide = parsed?.guide
    if (guide && ((Array.isArray(guide.steps) && guide.steps.length > 0) || guide.script))
      return guide
  }
  catch (error) {
    console.error('解析 helpManual 设置指南失败:', error)
  }
  return null
})

const guideVisible = ref(false)
const guideCopied = ref(false)

function openGuide() {
  guideVisible.value = true
}

async function copyGuideScript() {
  const script = atomGuide.value?.script
  if (!script)
    return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(script)
    }
    else {
      const textarea = document.createElement('textarea')
      textarea.value = script
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    guideCopied.value = true
    message.success('脚本已复制到剪贴板')
    setTimeout(() => {
      guideCopied.value = false
    }, 2000)
  }
  catch {
    message.error('复制失败，请手动全选复制')
  }
}

watch(() => flowStore.activeAtom, (newVal) => {
  if (!newVal?.key) {
    BUS.$emit('toggleAtomForm', false)
  }
  renderForm(newVal)
  console.log(atomTab.value)
})

watch(() => flowStore.selectedAtomIds, () => {
  activeKey.value = 0
})

watch(() => isShowFormItem.value, () => {
  atomTab.value = renderBaseConfig(atomTab.value)
})

function renderForm(val) {
  atomTab.value = val ? useBaseConfig(val, t) : []
}

function editSmartComp() {
  const processStore = useProcessStore()
  const smartId = getSmartComponentId(flowStore.activeAtom.key)
  const version = flowStore.activeAtom.version
  useRoutePush({
    name: SMARTCOMPONENT,
    query: {
      projectId: processStore.project.id,
      projectName: processStore.project.name,
      smartId,
      version,
    },
  })
}

onMounted(() => {
  if (flowStore.activeAtom)
    renderForm(flowStore.activeAtom)
})
</script>

<template>
  <section class="atom-config h-full relative bg-[#fff] dark:bg-[#1d1d1d]" :class="sidebarWide ? 'w-[620px]' : 'w-80'">
    <section v-if="atomTab.length > 0" class="relative atom-config-container h-full overflow-y-auto pt-3 pb-8 px-4">
      <div v-if="isSmartComponentKey(flowStore.activeAtom.key)" class="flex items-center mb-4">
        <rpa-icon name="magic-wand" size="20" class="text-primary" />
        <span class="ml-1 mr-auto text-[16px] font-medium">{{ $t('smartComponent.smartComponent') }}</span>
        <a-button type="primary" @click="editSmartComp">
          {{ $t('edit') }}
        </a-button>
      </div>
      <div class="flex items-center mb-4">
        <a-segmented v-model:value="activeKey" block :options="formattedTabs" class="flex-1">
          <template #label="{ title }">
            <span class="text-[12px]">{{ $t(title) }}</span>
          </template>
        </a-segmented>
        <rpa-hint-icon :name="sidebarWide ? 'sidebar-wide' : 'sidebar-narrow'" :title="sidebarWide ? '切换到窄版' : '切换到宽版'" class="ml-[12px]" width="16px" height="16px" enable-hover-bg @click="() => sidebarWide = !sidebarWide" />
      </div>
      <article
        v-for="item in atomTab[activeKey]?.params" :key="item.key"
        class="tab-container text-[#333] dark:text-[rgba(255,255,255,0.45)]"
      >
        <label v-if="item.name" class="tab-container-label dark:text-[rgba(255,255,255,0.85)] font-bold flex items-center">
          {{ item.name[i18next.language] }}
          <span
            v-if="item.key.startsWith('input') && atomGuide"
            class="ml-2 text-[12px] font-normal text-[#1677ff] dark:text-[#69b1ff] cursor-pointer hover:opacity-75 select-none"
            @click.stop="openGuide"
          >
            设置指南
          </span>
        </label>
        <AtomFormList :atom-form="item.formItems" />
      </article>
    </section>

    <a-modal
      v-model:open="guideVisible"
      :title="atomGuide?.title || '设置指南'"
      :width="720"
      :footer="null"
      class="atom-guide-modal"
    >
      <div class="atom-guide-content">
        <ol v-if="atomGuide?.steps?.length" class="atom-guide-steps">
          <li v-for="(step, index) in atomGuide.steps" :key="index" class="atom-guide-step text-[#333] dark:text-[rgba(255,255,255,0.85)]">
            {{ step }}
          </li>
        </ol>
        <div v-if="atomGuide?.script" class="atom-guide-script">
          <div class="atom-guide-script-header">
            <span class="atom-guide-script-title text-[#333] dark:text-[rgba(255,255,255,0.85)]">AirScript 脚本（全选复制后粘贴到 WPS 脚本编辑器）</span>
            <a-button size="small" type="primary" @click="copyGuideScript">
              {{ guideCopied ? '已复制' : '一键复制' }}
            </a-button>
          </div>
          <textarea
            :value="atomGuide.script"
            readonly
            class="atom-guide-script-textarea text-[#333] dark:text-[rgba(255,255,255,0.85)] bg-[#f5f5f5] dark:bg-[#2a2a2a] dark:border-[#444]"
            @click="($event.target as HTMLTextAreaElement).select()"
          />
        </div>
      </div>
    </a-modal>
  </section>
</template>

<style lang="scss" scoped>
.atom-config {
  .atom-config-container {
    opacity: 1;

    .tab-container {
      font-size: 12px;
      margin-bottom: 24px;

      .tab-container-label {
        font-size: 14px;
        margin-bottom: 12px;
      }
    }

    &::-webkit-scrollbar {
      width: 4px;
    }

    // &::-webkit-scrollbar-thumb {
    //   background: #ccc;
    // }

    :deep(.ant-tabs-tab) {
      padding: 8px 16px;
    }

    :deep(.ant-tabs-tabpane) {
      padding: 0 10px 10px;
    }
  }

  .atom-config-rectangle {
    width: 20px;
    height: 50px;
    left: -20px;
    line-height: 50px;
    margin-top: -45px;
    font-size: 20px;
    color: #7d7d7d;
    background: #f2f2f2;
    border-top-left-radius: 5px;
    border-bottom-left-radius: 5px;
    z-index: 3;
  }
}

.atom-guide-content {
  .atom-guide-steps {
    margin: 0 0 16px;
    padding-left: 20px;

    .atom-guide-step {
      margin-bottom: 8px;
      line-height: 1.6;
    }
  }

  .atom-guide-script-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    .atom-guide-script-title {
      font-weight: 500;
    }
  }

  .atom-guide-script-textarea {
    width: 100%;
    height: 320px;
    padding: 12px;
    box-sizing: border-box;
    font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    resize: vertical;
    outline: none;
    white-space: pre;

    &:focus {
      border-color: #1677ff;
    }
  }
}
</style>
