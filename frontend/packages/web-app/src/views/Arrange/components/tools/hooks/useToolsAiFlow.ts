import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'

import i18next from '@/plugins/i18next'

import { useRunningStore } from '@/stores/useRunningStore'
import type { ArrangeTools } from '@/views/Arrange/types/arrangeTools'

import { AiFlowModal } from '../aiFlowModal'

// AI 生成流程: 需求文本 → 云端 AI 从原子清单编排步骤 → 预览确认后依次插入流程
export function useToolsAiFlow() {
  const item: ArrangeTools = {
    key: 'aiGenerateFlow',
    title: 'arrange.aiFlowTitle',
    name: 'arrange.aiFlowName',
    fontSize: '',
    icon: 'magic-wand',
    action: 'design_ai_flow',
    loading: false,
    show: true,
    disable: () => ['debug', 'run'].includes(useRunningStore().running),
    clickFn: () => NiceModal.show(AiFlowModal),
    validateFn: ({ disable }) => {
      if (disable) {
        message.warning(i18next.t('arrange.stopRunningOrDebugFirst'))
        return false
      }
      return true
    },
  }

  return item
}
