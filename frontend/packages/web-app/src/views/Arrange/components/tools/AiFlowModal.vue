<script lang="ts" setup>
import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { computed, ref } from 'vue'

import { useFlowStore } from '@/stores/useFlowStore'
import { useProcessStore } from '@/stores/useProcessStore'
import { addAtomData } from '@/views/Arrange/components/flow/hooks/useFlow'
import { aiFillFlowParams, aiGenerateFlow, applyStepParams } from '@/views/Arrange/utils/aiFlow'
import type { AiFlowStep } from '@/views/Arrange/utils/aiFlow'
import { getAtomByKey, loopAtomByKey } from '@/views/Arrange/utils/generateData'

const modal = NiceModal.useModal()
const processStore = useProcessStore()
const flowStore = useFlowStore()
const { t } = useTranslation()

const requirement = ref('')
const generating = ref(false)
const inserting = ref(false)
const steps = ref<AiFlowStep[]>([])

// key → 原子标题(预览展示用), atomicTreeDataFlat 为拍平后的可用原子清单
const titleByKey = computed(() => {
  const map = new Map<string, string>()
  processStore.atomicTreeDataFlat.forEach((a: any) => map.set(a.key, a.title))
  return map
})

/**
 * AI 生成流程(两阶段): 需求 → 编排步骤(flow_generate) → 拉取所选原子参数 schema
 * 并让 AI 填值(flow_fill_params); 第二阶段失败降级为仅骨架(元素拾取类参数本就需手动选择)。
 */
async function handleGenerate() {
  const text = requirement.value.trim()
  if (!text || generating.value)
    return
  generating.value = true
  steps.value = []
  try {
    const result = await aiGenerateFlow(text, processStore.atomicTreeDataFlat)
    if (!result) {
      message.warning(t('arrange.aiFlowGenerateEmpty'))
      return
    }
    steps.value = await fillStepParams(text, result)
  }
  finally {
    generating.value = false
  }
}

/** 第二阶段参数填值: 逐个拉取原子能力 schema(单个失败跳过不影响其余步骤) */
async function fillStepParams(description: string, result: AiFlowStep[]): Promise<AiFlowStep[]> {
  const abilities: Record<string, any> = {}
  for (const step of result) {
    try {
      await loopAtomByKey(step.key)
      abilities[step.key] = getAtomByKey(step.key)
    }
    catch {
      // 单个原子能力拉取失败仅影响该步填参, 插入骨架不受影响
    }
  }
  return await aiFillFlowParams(description, result, abilities) ?? result
}

function paramCount(step: AiFlowStep) {
  return step.params ? Object.keys(step.params).length : 0
}

/**
 * 确认插入: 依次追加到流程末尾(多节点原子插入后列表长度变化, 每步重取末尾位置),
 * 插入后把 AI 填写的参数回填到节点 inputList 并持久化。
 */
async function handleInsert() {
  if (!steps.value.length || inserting.value)
    return
  inserting.value = true
  let filledCount = 0
  try {
    for (const step of steps.value) {
      const nodes = await addAtomData(step.key, flowStore.simpleFlowUIData.length)
      const node = Array.isArray(nodes) ? nodes[0] : null
      if (node && step.params) {
        filledCount += applyStepParams(node, step.params)
        persistNodeParams(node)
      }
    }
    message.success(t('arrange.aiFlowInsertDone', { count: steps.value.length, params: filledCount }))
    modal.hide()
  }
  finally {
    inserting.value = false
  }
}

/** 参数回填后持久化到流程文档并刷新节点必填校验状态 */
function persistNodeParams(node: any) {
  const idx = flowStore.simpleFlowUIData.findIndex(i => i.id === node.id)
  if (idx < 0)
    return
  flowStore.updataOriginFlowData([{ node, index: idx, process: processStore.activeProcessId }])
  flowStore.gainLastError(node.id)
}
</script>

<template>
  <a-modal
    v-bind="NiceModal.antdModal(modal)"
    destroy-on-close
    centered
    :width="560"
    :z-index="20"
    :title="$t('arrange.aiFlowTitle')"
    class="aiFlowModal"
    :keyboard="false"
    :mask-closable="false"
    :footer="null"
  >
    <div class="ai-flow-tip font-size-12">
      {{ $t('arrange.aiFlowTip') }}
    </div>
    <a-textarea
      v-model:value="requirement"
      :placeholder="$t('arrange.aiFlowPlaceholder')"
      :rows="3"
      :disabled="generating || inserting"
      class="mt-2"
    />
    <div class="flex justify-end mt-2">
      <a-button
        size="small"
        type="primary"
        :loading="generating"
        :disabled="!requirement.trim() || inserting"
        @click="handleGenerate"
      >
        {{ $t('arrange.aiFlowGenerate') }}
      </a-button>
    </div>
    <div v-if="steps.length" class="ai-flow-steps mt-3">
      <div v-for="(step, idx) in steps" :key="idx" class="ai-flow-step flex items-center">
        <span class="step-idx">{{ idx + 1 }}</span>
        <span class="step-title" :title="step.key">{{ titleByKey.get(step.key) || step.key }}</span>
        <span v-if="paramCount(step)" class="step-params">{{ $t('arrange.aiFlowParamsTag', { count: paramCount(step) }) }}</span>
        <span class="step-reason" :title="step.reason">{{ step.reason }}</span>
      </div>
      <div class="flex justify-end mt-3">
        <a-button size="small" :disabled="inserting" @click="modal.hide()">
          {{ $t('cancel') }}
        </a-button>
        <a-button
          size="small"
          type="primary"
          class="ml-2"
          :loading="inserting"
          @click="handleInsert"
        >
          {{ $t('arrange.aiFlowInsert') }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<style scoped lang="scss">
.ai-flow-tip {
  color: rgb(0 0 0 / 45%);
}

.ai-flow-steps {
  max-height: 280px;
  padding: 4px 8px;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
}

.ai-flow-step {
  padding: 3px 0;
  font-size: 12px;

  .step-idx {
    flex-shrink: 0;
    width: 20px;
    color: rgb(0 0 0 / 45%);
    text-align: right;
  }

  .step-title {
    flex-shrink: 0;
    max-width: 200px;
    margin-left: 8px;
    overflow: hidden;
    font-weight: 500;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .step-params {
    flex-shrink: 0;
    margin-left: 6px;
    padding: 0 6px;
    color: var(--primaryColor, #1677ff);
    background: rgb(22 119 255 / 8%);
    border-radius: 8px;
  }

  .step-reason {
    flex: 1;
    min-width: 0;
    margin-left: 8px;
    overflow: hidden;
    color: rgb(0 0 0 / 45%);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
