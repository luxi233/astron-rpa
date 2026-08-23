<script setup lang="ts">
import { CloseOutlined } from '@ant-design/icons-vue'
import { onMounted, ref } from 'vue'

import ConfigProvider from '@/components/ConfigProvider/index.vue'
import { WINDOW_NAME } from '@/constants'
import { utilsManager, windowManager } from '@/platform'
import LiveControlTree from '@/views/Arrange/components/pick/LiveControlTree.vue'

import { DEEP_PICK_EVENT, emitToMain } from './utils'

interface W2WType {
  from: WINDOW_NAME // 来源窗口
  target: WINDOW_NAME // 目标窗口
  type: DEEP_PICK_EVENT // 类型
  data?: any // 数据
}

// 实时树数据由主窗口经 w2w 转发(拾取 WS 会话在主窗口, 面板仅做展示与点选上报)
const liveTreeData = ref<any>(null)
// 点选捕获进行中: 防重复点击, 引擎 ack/捕获结果到达后由主窗口 FINISH 关窗或下一帧树推送解锁
const treePicking = ref(false)
// 树固定状态(引擎 Ctrl+点击 toggle): 固定后树不随鼠标刷新, 从容浏览/点选节点
const treeFrozen = ref(false)
// 选中节点 UIA 属性(右栏面板): 主窗口经 w2w 回传引擎查询结果, null=未查询/定位失败(前端回退节点自带字段)
const nodeProps = ref<Record<string, any> | null>(null)

utilsManager.listenEvent('w2w', ({ from, target, type, data }: W2WType) => {
  if (from !== WINDOW_NAME.MAIN || target !== WINDOW_NAME.DEEP_PICK)
    return
  if (type === DEEP_PICK_EVENT.TREE_UPDATE) {
    // 状态帧({frozen}): 只切提示文案, 不动树数据(固定期间保留树快照)
    if (data && typeof data.frozen === 'boolean') {
      treeFrozen.value = data.frozen
      return
    }
    treePicking.value = false
    // 树结构已刷新, 选中节点属性随旧树失效
    nodeProps.value = null
    liveTreeData.value = data
  }
  else if (type === DEEP_PICK_EVENT.TREE_PICK_RESULT) {
    // 点选 ack: 定位失败解锁可换节点重试(成功则引擎结束会话, 面板随 FINISH 关闭)
    treePicking.value = false
  }
  else if (type === DEEP_PICK_EVENT.TREE_PROPS_RESULT) {
    // 属性查询结果: null=定位失败, 面板回退显示节点自带字段
    nodeProps.value = data
  }
  else if (type === DEEP_PICK_EVENT.FINISH) {
    windowManager.closeWindow(WINDOW_NAME.DEEP_PICK)
  }
})

// 面板挂载即向主窗口报到: 首帧树推送可能先于本窗口监听注册到达(ipc 无排队即丢),
// 请求主窗口重发当前树快照, 兑现"打开面板即见全窗口列表"
onMounted(() => {
  emitToMain(DEEP_PICK_EVENT.READY)
})

// 树节点点选捕获: 属性链(窗口层→目标层)转发主窗口, 由拾取会话发给引擎完成捕获
function handlePickNode(chain: any[]) {
  if (treePicking.value)
    return
  treePicking.value = true
  emitToMain(DEEP_PICK_EVENT.TREE_PICK, chain)
}

// 选中节点查 UIA 属性: 属性链转发主窗口, 由拾取会话发给引擎(TREE_PROPS), 结果经 TREE_PROPS_RESULT 回显右栏
function handleSelectNode(chain: any[]) {
  emitToMain(DEEP_PICK_EVENT.TREE_PROPS, chain)
}

// 关闭面板 = 取消捕获: 通知主窗口销毁拾取会话(引擎会话随 WS 断连清理)
function handleClose() {
  emitToMain(DEEP_PICK_EVENT.CANCEL)
  windowManager.closeWindow(WINDOW_NAME.DEEP_PICK)
}
</script>

<template>
  <ConfigProvider>
    <div class="deep-pick-panel flex flex-col h-full">
      <div class="deep-pick-titlebar flex items-center">
        <span class="flex-1 truncate">{{ $t('deepCaptureLiveTree') }}</span>
        <a-button type="text" size="small" class="deep-pick-close" @click="handleClose">
          <template #icon>
            <CloseOutlined />
          </template>
        </a-button>
      </div>
      <div class="flex-1 overflow-hidden">
        <LiveControlTree :tree-data="liveTreeData" :pickable="!treePicking" :frozen="treeFrozen" :node-props="nodeProps" @pick-node="handlePickNode" @select-node="handleSelectNode" />
      </div>
    </div>
  </ConfigProvider>
</template>

<style scoped lang="scss">
.deep-pick-panel {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  overflow: hidden;
}

.deep-pick-titlebar {
  padding: 6px 8px 6px 12px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid #f0f0f0;
}

.deep-pick-close {
  flex-shrink: 0;
}
</style>
