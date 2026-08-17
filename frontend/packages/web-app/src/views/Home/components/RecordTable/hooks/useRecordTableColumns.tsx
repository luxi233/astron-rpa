import { Icon } from '@rpa/components'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { useTranslation } from 'i18next-vue'
import { h } from 'vue'

import { getDurationText } from '@/utils/dayjsUtils'

import { getlogs } from '@/api/record'
import { utilsManager } from '@/platform'
import OperMenu from '@/views/Home/components/OperMenu.vue'
import StatusCircle from '@/views/Home/components/StatusCircle.vue'
import { useCommonOperate } from '@/views/Home/pages/hooks/useCommonOperate.tsx'

import useRecordOperation from './useRecordOperation.tsx'

const LOG_LEVEL_MAP: Record<string, string> = {
  error: '错误',
  info: '信息',
  warning: '警告',
  debug: '调试',
}

export default function useRecordTableColumns(props?: { robotId?: string, taskId?: string }, refreshWithDelete?: (count: number) => void) {
  const translate = useTranslation()
  const { batchDelete } = useRecordOperation(refreshWithDelete)
  const { handleCheck, handleOpenDataTable } = useCommonOperate()

  // 导出执行日志为文本文件
  async function handleExportLog(record: any) {
    try {
      const res = await getlogs({ executeId: record.executeId })
      const rawLogs = JSON.parse(res.data || '[]') as Array<{ event_time: number, data: Record<string, any> }>
      if (!rawLogs.length) {
        message.warning(translate.t('noLogToExport'))
        return
      }
      const content = rawLogs
        .map(({ event_time, data }) => {
          const ts = dayjs(event_time * 1000).format('YYYY-MM-DD HH:mm:ss')
          const level = LOG_LEVEL_MAP[data.log_level] || data.log_level || ''
          const pos = data.process ? `[${data.process}:${data.line ?? '--'}] ` : ''
          const line = `[${ts}] [${level}] ${pos}${data.msg_str ?? ''}`
          return data.error_traceback ? `${line}\n${data.error_traceback}` : line
        })
        .join('\n')
      const fileName = `runlog-${record.robotName || record.executeId}-${dayjs(record.startTime).format('YYYYMMDD-HHmmss')}.txt`
      await utilsManager.saveFile(fileName, content)
      message.success(translate.t('common.operationSuccess'))
    }
    catch (e) {
      console.error('export log failed:', e)
      message.error(translate.t('exportLogFailed'))
    }
  }

  const projectMoreOpts = [
    {
      key: 'runningLog',
      text: translate.t('record.logDetail'),
      icon: h(<Icon name="log" size="16px" />),
      clickFn: record => handleCheck({ type: !props.robotId ? 'drawer' : 'modal', record }),
    },
    {
      key: 'exportLog',
      text: translate.t('exportLog'),
      icon: h(<Icon name="download" size="16px" />),
      clickFn: record => handleExportLog(record),
    },
    {
      key: 'runningDataTable',
      text: translate.t('dataSheet'),
      icon: h(<Icon name="sheet" size="16px" />),
      disableFn: record => !record.dataTablePath,
      clickFn: record => handleOpenDataTable(record),
    },
    {
      key: 'runningVideo',
      text: translate.t('record.videoPlay'),
      icon: h(<Icon name="video-play" size="16px" />),
      disableFn: record => !(record?.videoExist === '0'), // '0': 本地存在 '1': 本地不存在
      clickFn: record => utilsManager.playVideo(record.videoLocalPath),
    },
    {
      key: 'delete',
      text: translate.t('delete'),
      icon: h(<Icon name="market-del" size="16px" />),
      clickFn: record => batchDelete([record.executeId]),
    },
  ]

  const conditionColumns = []

  if (!props.robotId) {
    conditionColumns.push(
      {
        title: translate.t('robotName'),
        dataIndex: 'robotName',
        key: 'robotName',
        ellipsis: true,
      },
      {
        title: translate.t('record.version'),
        dataIndex: 'robotVersion',
        key: 'robotVersion',
        width: 60,
        ellipsis: true,
      },
    )
  }

  if (!(props.robotId || props.taskId)) {
    conditionColumns.push(
      {
        title: translate.t('taskName'),
        dataIndex: 'taskName',
        key: 'taskName',
        ellipsis: true,
        customRender: ({ record }) => record.taskName || '--',
      },
    )
  }

  const columns = [
    ...conditionColumns,
    {
      title: translate.t('startTime'),
      dataIndex: 'startTime',
      key: 'startTime',
      ellipsis: true,
      sorter: true,
    },
    {
      title: translate.t('endTime'),
      dataIndex: 'endTime',
      key: 'endTime',
      ellipsis: true,
      sorter: true,
    },
    {
      title: translate.t('record.duration'),
      key: 'executeTime',
      dataIndex: 'executeTime',
      customRender: ({ record }) => getDurationText(record.executeTime),
    },
    {
      title: translate.t('result'),
      dataIndex: 'result',
      key: 'result',
      ellipsis: true,
      width: 100,
      customRender: ({ record }) => <StatusCircle type={String(record.result)} />,
    },
    {
      title: translate.t('operate'),
      dataIndex: 'oper',
      key: 'oper',
      width: 120,
      customRender: ({ record }) => <OperMenu row={record} moreOpts={projectMoreOpts} />,
    },
  ]

  return { columns: columns.filter(i => i) }
}
