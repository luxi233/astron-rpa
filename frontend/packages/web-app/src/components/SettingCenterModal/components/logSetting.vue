<script setup lang="ts">
import { Button, Form, message, Modal, Select, Table } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import dayjs from 'dayjs'
import { onMounted, ref } from 'vue'

import { clearRunLog, getRunLogDownloadUrl, getRunLogList } from '@/api/setting'
import type { RunLogItem } from '@/api/setting'
import useUserSettingStore from '@/stores/useUserSetting'

import Card from './card.vue'

const { t } = useTranslation()
const userSetting = useUserSettingStore()

const logForm = ref<{
  level: 'off' | 'standard' | 'debug'
  retentionDays: number
}>({
  level: userSetting.userSetting.logSetting?.level || 'standard',
  retentionDays: userSetting.userSetting.logSetting?.retentionDays || 30,
})

const levelOptions = ref([
  { label: t('settingCenter.logSetting.levelOff'), value: 'off' },
  { label: t('settingCenter.logSetting.levelStandard'), value: 'standard' },
  { label: t('settingCenter.logSetting.levelDebug'), value: 'debug' },
])

const retentionOptions = [1, 3, 7, 15, 30, 60, 90, 180, 360].map(d => ({
  label: t('settingCenter.logSetting.days', { count: d }),
  value: d,
}))

function handleLevelChange(level: 'off' | 'standard' | 'debug') {
  userSetting.changeLogSetting({ level })
}

function handleRetentionChange(retentionDays: number) {
  userSetting.changeLogSetting({ retentionDays })
}

// 日志文件列表
const logList = ref<RunLogItem[]>([])
const loading = ref(false)

async function refreshLogList() {
  loading.value = true
  try {
    const res = await getRunLogList()
    logList.value = res.list || []
  }
  catch (e) {
    console.error(e)
  }
  finally {
    loading.value = false
  }
}

function formatSize(size: number) {
  if (size < 1024)
    return `${size} B`
  if (size < 1024 * 1024)
    return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const columns = [
  { title: () => t('settingCenter.logSetting.fileName'), dataIndex: 'exec_id', key: 'exec_id', ellipsis: true },
  { title: () => t('settingCenter.logSetting.project'), dataIndex: 'project_id', key: 'project_id', ellipsis: true, width: 110 },
  { title: () => t('settingCenter.logSetting.size'), dataIndex: 'size', key: 'size', width: 90 },
  { title: () => t('settingCenter.logSetting.mtime'), dataIndex: 'mtime', key: 'mtime', width: 160 },
  { title: () => t('settingCenter.logSetting.action'), key: 'action', width: 70 },
]

function handleDownload(record: RunLogItem) {
  window.open(getRunLogDownloadUrl(record.path))
}

// 手动清理: 按保留时限清理过期日志
async function handleClearExpired() {
  try {
    const res = await clearRunLog({ before_days: logForm.value.retentionDays })
    message.success(t('settingCenter.logSetting.cleared', { count: res.data?.removed ?? 0 }))
    refreshLogList()
  }
  catch (e) {
    console.error(e)
  }
}

// 清空全部日志
function handleClearAll() {
  Modal.confirm({
    title: t('settingCenter.logSetting.clearAll'),
    content: t('settingCenter.logSetting.clearAllConfirm'),
    okText: t('confirm'),
    okType: 'danger',
    cancelText: t('cancel'),
    async onOk() {
      try {
        const res = await clearRunLog({})
        message.success(t('settingCenter.logSetting.cleared', { count: res.data?.removed ?? 0 }))
        refreshLogList()
      }
      catch (e) {
        console.error(e)
      }
    },
  })
}

onMounted(refreshLogList)
</script>

<template>
  <Card
    :title="$t('settingCenter.logSetting.title')"
    :description="$t('settingCenter.logSetting.subtitle')"
    class="h-[84px] px-[20px] py-[17px]"
  />
  <Form label-align="left" :colon="false">
    <div class="space-y-6 py-6 px-5">
      <div class="flex items-center">
        {{ $t('settingCenter.logSetting.level') }}
        <Select
          v-model:value="logForm.level"
          class="w-[120px] mx-2"
          :options="levelOptions"
          @change="handleLevelChange"
        />
        <span class="text-xs text-[rgba(0,0,0,0.45)] dark:text-[rgba(255,255,255,0.45)]">
          {{ $t('settingCenter.logSetting.levelDesc') }}
        </span>
      </div>
      <div class="flex items-center">
        {{ $t('settingCenter.logSetting.retention') }}
        <Select
          v-model:value="logForm.retentionDays"
          class="w-[120px] mx-2"
          :options="retentionOptions"
          @change="handleRetentionChange"
        />
        <span class="text-xs text-[rgba(0,0,0,0.45)] dark:text-[rgba(255,255,255,0.45)]">
          {{ $t('settingCenter.logSetting.retentionDesc') }}
        </span>
      </div>
      <div class="flex items-center gap-3">
        <Button size="small" @click="handleClearExpired">
          {{ $t('settingCenter.logSetting.cleanup') }}
        </Button>
        <Button size="small" danger @click="handleClearAll">
          {{ $t('settingCenter.logSetting.clearAll') }}
        </Button>
        <Button size="small" type="link" @click="refreshLogList">
          {{ $t('settingCenter.logSetting.refresh') }}
        </Button>
      </div>
    </div>
  </Form>
  <div class="px-5 pb-4">
    <div class="text-sm font-semibold mb-2">
      {{ $t('settingCenter.logSetting.fileList') }}
      ({{ logList.length }})
    </div>
    <Table
      size="small"
      :columns="columns"
      :data-source="logList"
      :loading="loading"
      :pagination="{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }"
      :locale="{ emptyText: $t('settingCenter.logSetting.empty') }"
      row-key="path"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'size'">
          {{ formatSize(record.size) }}
        </template>
        <template v-else-if="column.key === 'mtime'">
          {{ dayjs(record.mtime * 1000).format('YYYY-MM-DD HH:mm:ss') }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="handleDownload(record as RunLogItem)">{{ $t('settingCenter.logSetting.download') }}</a>
        </template>
      </template>
    </Table>
  </div>
</template>
