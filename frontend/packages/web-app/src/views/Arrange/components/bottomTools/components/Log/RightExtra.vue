<script lang="ts" setup>
import { message } from 'ant-design-vue'
import { to } from 'await-to-js'
import dayjs from 'dayjs'
import { useTranslation } from 'i18next-vue'

import { utilsManager } from '@/platform'
import { useRunlogStore } from '@/stores/useRunlogStore'

const { t } = useTranslation()

function clearLog() {
  useRunlogStore().clearLogs()
}

async function exportLog() {
  const list = useRunlogStore().logList
  if (!list.length) {
    message.warning(t('noLogToExport'))
    return
  }

  const content = list
    .map((l) => {
      const pos = l.processName ? `[${l.processName}:${l.lineNum ?? '--'}] ` : ''
      return `[${l.timestamp}] [${l.logLevelText}] ${pos}${l.content}`
    })
    .join('\n')
  const fileName = `runlog-${dayjs().format('YYYYMMDD-HHmmss')}.txt`

  const [error, saved] = await to<boolean, string>(utilsManager.saveFile(fileName, content))
  if (error)
    message.error(error)
  else if (saved)
    message.success(t('common.operationSuccess'))
}
</script>

<template>
  <div class="flex items-center gap-1">
    <rpa-hint-icon
      name="download"
      :title="$t('exportLog')"
      enable-hover-bg
      @click="() => exportLog()"
    />
    <rpa-hint-icon
      name="clear-outlined"
      title="清除日志"
      enable-hover-bg
      @click="() => clearLog()"
    />
  </div>
</template>
