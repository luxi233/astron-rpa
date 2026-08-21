<script lang="ts" setup>
import { CloseOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { h, onMounted, ref } from 'vue'

import { usePickStore } from '@/stores/usePickStore'

const modal = NiceModal.useModal()
const usePick = usePickStore()
const { t } = useTranslation()

interface HealEntry {
  key: string
  app: string
  relaxations: string[]
  pathLen: number
  ts: string
}

const loading = ref(false)
const dropping = ref(false)
const metrics = ref<Record<string, number>>({})
const healCache = ref<HealEntry[]>([])

// 指标键 -> i18n 文案(last_locate_ms 带 ms 后缀单独处理)
const metricLabels: [string, string][] = [
  ['locate_total', 'pickerMetricLocateTotal'],
  ['locate_success', 'pickerMetricLocateSuccess'],
  ['locate_fail', 'pickerMetricLocateFail'],
  ['heal_attempt', 'pickerMetricHealAttempt'],
  ['heal_success', 'pickerMetricHealSuccess'],
  ['heal_cache_hit', 'pickerMetricHealCacheHit'],
  ['heal_cache_invalidated', 'pickerMetricHealCacheInvalidated'],
  ['cv_fallback_attempt', 'pickerMetricCvAttempt'],
  ['cv_fallback_success', 'pickerMetricCvSuccess'],
  ['last_locate_ms', 'pickerMetricLastMs'],
]

function metricValue(key: string) {
  const val = metrics.value[key] ?? 0
  return key === 'last_locate_ms' ? `${val} ms` : String(val)
}

/**
 * 拉取指标与自愈缓存(独立 WS 会话, 与批量校验同款模式)
 */
function load() {
  loading.value = true
  usePick.pickerMetrics((res) => {
    loading.value = false
    if (!res.success)
      return
    metrics.value = res.data?.metrics || {}
    healCache.value = Object.entries(res.data?.heal_cache || {}).map(([key, entry]: [string, any]) => ({
      key,
      app: entry?.app || '-',
      relaxations: entry?.relaxations || [],
      pathLen: (entry?.path || []).length,
      ts: entry?.ts ? new Date(entry.ts * 1000).toLocaleString() : '-',
    }))
  })
}

function handleDrop(entry: HealEntry) {
  dropping.value = true
  usePick.healCacheDrop(entry.key, (res) => {
    dropping.value = false
    if (res.success && res.data?.dropped)
      message.success(t('healCacheDropSuccess'))
    else
      message.warning(t('healCacheDropMiss'))
    load()
  })
}

function handleClose() {
  if (loading.value)
    return
  modal.hide()
}

onMounted(load)
</script>

<template>
  <a-modal
    v-bind="NiceModal.antdModal(modal)"
    destroy-on-close
    centered
    :width="720"
    :z-index="20"
    :title="$t('pickerMetrics')"
    class="pickerMetricsModal"
    :keyboard="false"
    :mask-closable="false"
    :footer="null"
  >
    <template #closeIcon>
      <CloseOutlined @click.stop="handleClose" />
    </template>
    <div class="picker-metrics-toolbar flex items-center justify-between mb-2">
      <span class="tip font-size-12">{{ $t('pickerMetricsTip') }}</span>
      <a-button
        size="small"
        type="primary"
        :icon="h(ReloadOutlined)"
        :loading="loading"
        class="font-size-12 inline-flex-center"
        @click="load"
      >
        {{ $t('pickerMetricsRefresh') }}
      </a-button>
    </div>
    <a-spin :spinning="loading || dropping">
      <div class="metric-grid mb-3">
        <div v-for="[key, label] in metricLabels" :key="key" class="metric-card border border-border">
          <div class="metric-value">
            {{ metricValue(key) }}
          </div>
          <div class="metric-label">
            {{ $t(label) }}
          </div>
        </div>
      </div>
      <div class="section-title font-size-12 mb-1">
        {{ $t('healCacheTitle') }}
      </div>
      <div class="heal-cache-wrapper border border-border">
        <a-table
          v-if="healCache.length"
          :data-source="healCache"
          :pagination="false"
          size="small"
          row-key="key"
          :scroll="{ y: 280 }"
        >
          <a-table-column :title="$t('healCacheApp')" data-index="app" :width="120" ellipsis />
          <a-table-column :title="$t('healCacheRelaxations')">
            <template #default="{ record }">
              <span class="font-size-12">{{ record.relaxations.length ? record.relaxations.join('；') : '-' }}</span>
            </template>
          </a-table-column>
          <a-table-column :title="$t('healCachePathLen')" data-index="pathLen" :width="80" align="center" />
          <a-table-column :title="$t('healCacheTime')" data-index="ts" :width="160" />
          <a-table-column :title="$t('healCacheAction')" :width="80" align="center">
            <template #default="{ record }">
              <a-popconfirm :title="$t('healCacheDropConfirm')" @confirm="handleDrop(record)">
                <a-button size="small" type="link" danger :icon="h(DeleteOutlined)" />
              </a-popconfirm>
            </template>
          </a-table-column>
        </a-table>
        <a-empty v-else-if="!loading" class="mt-10" :description="$t('healCacheEmpty')" />
      </div>
    </a-spin>
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

.picker-metrics-toolbar .tip {
  color: rgb(0 0 0 / 45%);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.metric-card {
  padding: 8px 4px;
  text-align: center;
  border-radius: 2px;

  .metric-value {
    font-size: 18px;
    font-weight: 600;
    color: $color-primary;
  }

  .metric-label {
    margin-top: 2px;
    font-size: 12px;
    color: rgb(0 0 0 / 45%);
  }
}

.section-title {
  font-weight: 600;
}

.heal-cache-wrapper {
  min-height: 120px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}
</style>
