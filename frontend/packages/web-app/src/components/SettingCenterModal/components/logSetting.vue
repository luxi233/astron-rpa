<script setup lang="ts">
import { Button, Form, message, Modal, Select, Spin, Table } from 'ant-design-vue'
import dayjs from 'dayjs'
import { useTranslation } from 'i18next-vue'
import { nextTick, onMounted, ref } from 'vue'

import { clearEngineLog, clearRunLog, getEngineLogList, getRunLogDownloadUrl, getRunLogList, readEngineLog } from '@/api/setting'
import type { EngineLogItem, RunLogItem } from '@/api/setting'
import { utilsManager } from '@/platform'
import useUserSettingStore from '@/stores/useUserSetting'

import Card from './card.vue'

const { t } = useTranslation()
const userSetting = useUserSettingStore()

const logForm = ref<{
  level: 'off' | 'standard' | 'debug'
  runRetentionDays: number
  engineRetentionDays: number
}>({
  level: userSetting.userSetting.logSetting?.level || 'standard',
  runRetentionDays: userSetting.userSetting.logSetting?.runRetentionDays || 30,
  engineRetentionDays: userSetting.userSetting.logSetting?.engineRetentionDays || 7,
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

function handleRunRetentionChange(runRetentionDays: number) {
  userSetting.changeLogSetting({ runRetentionDays })
}

function handleEngineRetentionChange(engineRetentionDays: number) {
  userSetting.changeLogSetting({ engineRetentionDays })
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

// 手动清理: 流程日志与引擎日志分别按各自的保留时限清理
async function handleClearExpired() {
  try {
    const [runRes, engineRes] = await Promise.all([
      clearRunLog({ before_days: logForm.value.runRetentionDays }),
      clearEngineLog({ before_days: logForm.value.engineRetentionDays }),
    ])
    const count = (runRes.data?.removed ?? 0) + (engineRes.data?.removed ?? 0)
    message.success(t('settingCenter.logSetting.cleared', { count }))
    refreshLogList()
    refreshEngineLogList()
  }
  catch (e) {
    console.error(e)
  }
}

// 清空全部日志(流程日志+引擎日志, 引擎侧保护正在写入的文件)
function handleClearAll() {
  Modal.confirm({
    title: t('settingCenter.logSetting.clearAll'),
    content: t('settingCenter.logSetting.clearAllConfirm'),
    okText: t('confirm'),
    okType: 'danger',
    cancelText: t('cancel'),
    async onOk() {
      try {
        const [runRes, engineRes] = await Promise.all([
          clearRunLog({}),
          clearEngineLog({}),
        ])
        const count = (runRes.data?.removed ?? 0) + (engineRes.data?.removed ?? 0)
        message.success(t('settingCenter.logSetting.cleared', { count }))
        refreshLogList()
        refreshEngineLogList()
      }
      catch (e) {
        console.error(e)
      }
    },
  })
}

onMounted(refreshLogList)

// ===== 引擎日志(设计器/执行器/调度器自身日志) =====
const engineLogDir = ref('')
const engineLogList = ref<EngineLogItem[]>([])
const engineLoading = ref(false)

const engineColumns = [
  { title: () => t('settingCenter.logSetting.fileName'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: () => t('settingCenter.logSetting.size'), dataIndex: 'size', key: 'size', width: 90 },
  { title: () => t('settingCenter.logSetting.mtime'), dataIndex: 'mtime', key: 'mtime', width: 160 },
  { title: () => t('settingCenter.logSetting.action'), key: 'action', width: 70 },
]

async function refreshEngineLogList() {
  engineLoading.value = true
  try {
    const res = await getEngineLogList()
    engineLogList.value = res.list || []
    engineLogDir.value = res.dir || ''
  }
  catch (e) {
    console.error(e)
  }
  finally {
    engineLoading.value = false
  }
}

function handleOpenEngineLogDir() {
  if (!engineLogDir.value)
    return
  utilsManager.shellopen(engineLogDir.value)
}

// 查看弹窗
const viewerOpen = ref(false)
const viewerLoading = ref(false)
const viewerFile = ref('')
const viewerLines = ref<string[]>([])
const viewerTruncated = ref(false)
const tailLines = ref(500)
const tailOptions = [200, 500, 1000, 3000, 5000].map(n => ({ label: String(n), value: n }))
const viewerBodyRef = ref<HTMLElement>()

async function handleViewEngineLog(record: EngineLogItem) {
  viewerFile.value = record.name
  viewerOpen.value = true
  await loadEngineLogContent()
}

async function loadEngineLogContent() {
  if (!viewerFile.value)
    return
  viewerLoading.value = true
  try {
    const res = await readEngineLog({ filename: viewerFile.value, tail_lines: tailLines.value })
    viewerLines.value = res.lines || []
    viewerTruncated.value = !!res.truncated
    await nextTick(() => {
      // 自动滚动到底部(最新日志)
      if (viewerBodyRef.value)
        viewerBodyRef.value.scrollTop = viewerBodyRef.value.scrollHeight
    })
  }
  catch (e) {
    console.error(e)
    viewerLines.value = []
  }
  finally {
    viewerLoading.value = false
  }
}

onMounted(refreshEngineLogList)
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
        {{ $t('settingCenter.logSetting.runRetention') }}
        <Select
          v-model:value="logForm.runRetentionDays"
          class="w-[120px] mx-2"
          :options="retentionOptions"
          @change="handleRunRetentionChange"
        />
      </div>
      <div class="flex items-center">
        {{ $t('settingCenter.logSetting.engineRetention') }}
        <Select
          v-model:value="logForm.engineRetentionDays"
          class="w-[120px] mx-2"
          :options="retentionOptions"
          @change="handleEngineRetentionChange"
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

  <!-- 引擎日志(设计器/执行器/调度器自身日志) -->
  <div class="px-5 pb-4">
    <div class="flex items-center justify-between mb-2">
      <div class="text-sm font-semibold">
        {{ $t('settingCenter.logSetting.engineFileList') }}
        ({{ engineLogList.length }})
      </div>
      <div class="flex items-center gap-3">
        <a @click="handleOpenEngineLogDir">{{ $t('settingCenter.logSetting.openLogDir') }}</a>
        <a @click="refreshEngineLogList">{{ $t('settingCenter.logSetting.refresh') }}</a>
      </div>
    </div>
    <div class="text-xs text-[rgba(0,0,0,0.45)] dark:text-[rgba(255,255,255,0.45)] mb-2">
      {{ $t('settingCenter.logSetting.engineLogDesc') }}
    </div>
    <Table
      size="small"
      :columns="engineColumns"
      :data-source="engineLogList"
      :loading="engineLoading"
      :pagination="{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }"
      :locale="{ emptyText: $t('settingCenter.logSetting.empty') }"
      row-key="name"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'size'">
          {{ formatSize(record.size) }}
        </template>
        <template v-else-if="column.key === 'mtime'">
          {{ dayjs(record.mtime * 1000).format('YYYY-MM-DD HH:mm:ss') }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="handleViewEngineLog(record as EngineLogItem)">{{ $t('settingCenter.logSetting.view') }}</a>
        </template>
      </template>
    </Table>
  </div>

  <!-- 引擎日志查看弹窗 -->
  <Modal
    v-model:open="viewerOpen"
    :title="`${$t('settingCenter.logSetting.engineLogView')} - ${viewerFile}`"
    :width="860"
    :footer="null"
  >
    <div class="flex items-center gap-2 mb-2">
      <span class="text-xs">{{ $t('settingCenter.logSetting.tailLines') }}</span>
      <Select v-model:value="tailLines" :options="tailOptions" size="small" class="w-24" @change="loadEngineLogContent" />
      <a class="ml-2" @click="loadEngineLogContent">{{ $t('settingCenter.logSetting.refresh') }}</a>
      <span v-if="viewerTruncated" class="text-xs text-[#faad14] ml-2">
        {{ $t('settingCenter.logSetting.fileTooLarge') }}
      </span>
    </div>
    <Spin :spinning="viewerLoading">
      <div
        ref="viewerBodyRef"
        class="engine-log-viewer font-mono text-xs leading-5 whitespace-pre overflow-auto p-2 rounded bg-[#fafafa] dark:bg-[rgba(255,255,255,0.06)] text-[rgba(0,0,0,0.85)] dark:text-[rgba(255,255,255,0.85)]"
      >
        {{ viewerLines.join('\n') }}
      </div>
    </Spin>
  </Modal>
</template>

<style lang="scss" scoped>
.engine-log-viewer {
  height: 60vh;
}
</style>
