<script lang="ts" setup>
import { AimOutlined, CheckCircleOutlined, CloseCircleOutlined, CloseOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { computed, h, ref } from 'vue'

import { useElementsStore } from '@/stores/useElementsStore'
import { usePickStore } from '@/stores/usePickStore'

const modal = NiceModal.useModal()
const useElements = useElementsStore()
const usePick = usePickStore()
const { t } = useTranslation()

interface CvCandidate {
  rect: number[]
  score: number
}

interface BatchReport {
  id: string
  name: string
  success: boolean
  note?: string
  error?: string
  cv_candidates?: CvCandidate[]
}

const reports = ref<BatchReport[]>([])
const validating = computed(() => usePick.isChecking)

// ---- I1: CV 歧义交互式消歧(嵌套候选选择弹窗) ----
const disambiguateVisible = ref(false)
const disambiguating = ref(false)
const currentRecord = ref<BatchReport | null>(null)
const selectedCandidate = ref<number>(0)

function openDisambiguate(record: BatchReport) {
  currentRecord.value = record
  selectedCandidate.value = 0
  disambiguateVisible.value = true
}

function confirmDisambiguate() {
  const record = currentRecord.value
  if (!record || !record.cv_candidates?.length)
    return
  const cand = record.cv_candidates[selectedCandidate.value]
  if (!cand) {
    message.warning(t('cvDisambiguateSelectFirst'))
    return
  }
  disambiguating.value = true
  usePick.cvDisambiguate({ id: record.id, name: record.name, rect: cand.rect, score: cand.score }, (res) => {
    disambiguating.value = false
    if (res.success && res.data?.success) {
      // 选定候选后该项按坐标定位成功(一次性决策, 不写自愈缓存)
      record.success = true
      record.note = t('cvDisambiguateDone')
      delete record.error
      delete record.cv_candidates
      disambiguateVisible.value = false
    }
  })
}

// 元素库扁平化(分组 → 元素列表)
const allElements = computed(() => {
  const list: any[] = []
  useElements.elements.forEach((group: any) => {
    ;(group.elements || []).forEach((ele: any) => list.push(ele))
  })
  return list
})

const passedCount = computed(() => reports.value.filter(r => r.success).length)

/**
 * 开始批量校验: 全库元素逐项定位检查(与运行时行为一致, 含自愈/CV 降级)
 */
function handleStart() {
  const items = allElements.value.map(ele => ({
    id: ele.id,
    name: ele.name,
    element: ele.elementData,
  }))
  if (!items.length) {
    message.info(t('noData'))
    return
  }
  reports.value = []
  usePick.batchValidate(items, (res) => {
    if (res.success)
      reports.value = res.data
  })
}

function handleClose() {
  if (validating.value)
    return
  modal.hide()
}
</script>

<template>
  <a-modal
    v-bind="NiceModal.antdModal(modal)"
    destroy-on-close
    centered
    :width="620"
    :z-index="20"
    :title="$t('batchValidate')"
    class="batchValidateModal"
    :keyboard="false"
    :mask-closable="false"
    :footer="null"
  >
    <template #closeIcon>
      <CloseOutlined @click.stop="handleClose" />
    </template>
    <div class="batch-validate-toolbar flex items-center justify-between mb-2">
      <span class="tip font-size-12">{{ $t('batchValidateTip') }}</span>
      <div class="flex items-center">
        <span v-if="reports.length" class="font-size-12 mr-2">
          {{ $t('batchValidateSummary') }}: {{ passedCount }}/{{ reports.length }}
        </span>
        <a-button
          size="small"
          type="primary"
          :icon="h(ThunderboltOutlined)"
          :loading="validating"
          :disabled="!allElements.length"
          class="font-size-12 inline-flex-center"
          @click="handleStart"
        >
          {{ $t('batchValidateStart') }}
        </a-button>
      </div>
    </div>
    <div class="batch-validate-wrapper border border-border">
      <a-spin :spinning="validating">
        <a-table
          v-if="reports.length"
          :data-source="reports"
          :pagination="false"
          size="small"
          row-key="id"
          :scroll="{ y: 360 }"
        >
          <a-table-column :title="$t('elementName')" data-index="name" :width="180">
            <template #default="{ record }">
              <span class="font-size-12">{{ record.name }}</span>
            </template>
          </a-table-column>
          <a-table-column :title="$t('batchValidateStatus')" :width="90">
            <template #default="{ record }">
              <span v-if="record.success" class="font-size-12 status-pass">
                <CheckCircleOutlined /> {{ $t('batchValidatePass') }}
              </span>
              <span v-else class="font-size-12 status-fail">
                <CloseCircleOutlined /> {{ $t('batchValidateFail') }}
              </span>
            </template>
          </a-table-column>
          <a-table-column :title="$t('batchValidateNote')">
            <template #default="{ record }">
              <span class="font-size-12">{{ record.note || record.error || '-' }}</span>
              <a-button
                v-if="record.cv_candidates && record.cv_candidates.length"
                size="small"
                type="link"
                :icon="h(AimOutlined)"
                class="font-size-12 inline-flex-center"
                @click="openDisambiguate(record)"
              >
                {{ $t('cvDisambiguate') }}
              </a-button>
            </template>
          </a-table-column>
        </a-table>
        <a-empty
          v-else-if="!validating"
          class="mt-10"
          :description="$t('batchValidateEmpty')"
        />
      </a-spin>
    </div>
    <!-- I1: CV 歧义候选选择(嵌套弹窗, 放弃即关闭维持安全语义) -->
    <a-modal
      v-model:open="disambiguateVisible"
      :title="$t('cvDisambiguateTitle')"
      :width="480"
      :z-index="30"
      :confirm-loading="disambiguating"
      :ok-text="$t('cvDisambiguateConfirm')"
      :cancel-text="$t('cvDisambiguateGiveUp')"
      @ok="confirmDisambiguate"
    >
      <p class="disambiguate-tip font-size-12 mb-2">
        {{ $t('cvDisambiguateTip') }}
      </p>
      <a-radio-group v-model:value="selectedCandidate">
        <div v-for="(cand, i) in currentRecord?.cv_candidates" :key="i" class="mb-1">
          <a-radio :value="i">
            <span class="font-size-12">
              {{ $t('cvDisambiguateCandidate') }} {{ i + 1 }}
              （{{ $t('cvDisambiguateScore') }} {{ cand.score }}，{{ $t('cvDisambiguateRect') }} [{{ cand.rect.join(', ') }}]）
            </span>
          </a-radio>
        </div>
      </a-radio-group>
    </a-modal>
  </a-modal>
</template>

<style scoped lang="scss">
.font-size-12 {
  font-size: 12px;
}
.inline-flex-center {
  display: inline-flex;
  align-items: center;
}

.batch-validate-toolbar .tip {
  color: rgb(0 0 0 / 45%);
}

.batch-validate-wrapper {
  min-height: 200px;
  max-height: 420px;
  overflow-y: auto;
  padding: 4px;
}

.status-pass {
  color: #52c41a;
}

.status-fail {
  color: #ff4d4f;
}

.disambiguate-tip {
  color: rgb(0 0 0 / 45%);
}
</style>
