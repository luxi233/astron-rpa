import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

import BUS from '@/utils/eventBus'
import $loading from '@/utils/globalLoading'

import { RpaPicker } from '@/api/pick'
import { windowManager } from '@/platform'
import { useElementsStore } from '@/stores/useElementsStore'
import type { PickParams } from '@/types/resource'
import { ElementPickModal } from '@/views/Arrange/components/pick'

import { useVariableStore } from './useVariableStore'

export const usePickStore = defineStore('pickStore', () => {
  const isPicking = ref(false) // 正在拾取
  const isChecking = ref(false) // 正在校验
  const isDataPicking = ref(false) // 正在数据抓取
  const isTreeLoading = ref(false) // 控件树浏览器加载中
  const pickerType = ref('')
  // 深度捕获实时控件树(I5): 捕获进行中主窗口收缩为右侧面板, 随鼠标推送增量树
  const isDeepPicking = ref(false)
  const liveTreeData = ref<any>(null)

  const variableStore = useVariableStore()
  const { t } = useTranslation()
  const useElements = useElementsStore()
  const elementPickModal = NiceModal.useModal(ElementPickModal)

  const pickTypeMap = {
    '': 'ELEMENT', // 普通拾取
    'ELEMENT': 'ELEMENT', // 普通拾取
    'WEBPICK': 'ELEMENT', // web拾取
    'WINPICK': 'ELEMENT', // win拾取
    'SIMILAR': 'SIMILAR', // 相似拾取
    'CV': 'CV',
    'WINDOW': 'WINDOW', // 窗口拾取
    'POINT': 'POINT', // 坐标点拾取
    'BATCH': 'BATCH', // 批量抓取
  }
  const validTypeMap = {
    '': 'ELEMENT', // 普通拾取
    'ELEMENT': 'ELEMENT', // 普通拾取
    'WEBPICK': 'ELEMENT', // web拾取
    'WINPICK': 'ELEMENT', // win拾取
    'SIMILAR': 'ELEMENT', // 相似拾取
    'CV': 'CV',
    'WINDOW': 'WINDOW', // 窗口拾取
    'POINT': 'POINT', // 坐标点拾取
  }
  // 深度捕获侧边栏形态: 主窗口不最小化, 收缩为屏幕右侧 320px 置顶面板承载实时树
  const DEEP_SIDEBAR_WIDTH = 320
  async function enterDeepSidebarMode() {
    try {
      const workArea: any = await windowManager.getScreenWorkArea()
      const scale = await windowManager.scaleFactor()
      const width = workArea?.width || window.screen.availWidth
      const height = workArea?.height || window.screen.availHeight
      // setWindowPosition 为物理像素, 需乘缩放系数; 宽度用物理像素保持面板实际 320dp
      const physWidth = Math.round(DEEP_SIDEBAR_WIDTH * scale)
      await windowManager.setWindowPosition((workArea?.x || 0) + (width - DEEP_SIDEBAR_WIDTH) * scale, (workArea?.y || 0) * scale)
      await windowManager.setWindowSize({ width: physWidth, height: Math.round(height * scale) })
      await windowManager.setWindowAlwaysOnTop(true)
    }
    catch {
      // 收缩失败降级为最小化, 不阻断拾取
      windowManager.minimizeWindow()
    }
  }

  // 拾取结束
  function finishPick() {
    isPicking.value = false
    isDeepPicking.value = false
    liveTreeData.value = null
    RpaPicker.destroy()
    windowManager.setWindowAlwaysOnTop(false)
    windowManager.maximizeWindow(true)
  }
  // 校验结束
  function finishCheck(finshType = 'maximize') {
    isChecking.value = false
    RpaPicker.destroy()
    finshType === 'maximize' ? windowManager.maximizeWindow(true) : windowManager.restoreWindow()
  }
  // 开始鼠标位置拾取
  const startMousePick = (callback: (params: { success: boolean, data: any }) => void) => {
    // 启动拾取
    RpaPicker.create(() => {
      const _pickType = pickTypeMap.POINT
      pickerType.value = _pickType
      setTimeout(() => {
        const sendParams: PickParams = {
          pick_sign: 'START',
          pick_type: _pickType,
          data: '',
        }
        RpaPicker.send(sendParams)
        windowManager.minimizeWindow()
      }, 500)
    })
    // 绑定消息
    RpaPicker.bindMessage((res) => {
      const { key, data, err_msg } = res || {} // key: 'success' | 'error' | 'ping'
      console.log('startPick res: ', res)
      if (key === 'success' && data) {
        const dataObj = JSON.parse(data)
        callback && callback({
          success: true,
          data: dataObj,
        })
        finishPick()
      }
      if (key === 'error') {
        const errorMsg = data || err_msg || t('rpaPickerUnavailable')
        message.error(errorMsg)
        finishPick()
      }
      if (key === 'cancel') {
        finishPick()
      }
    })
    // 绑定关闭
    RpaPicker.bindClose(() => {
      callback
      && callback({
        success: false,
        data: null,
      })
      finishPick()
    })
    // 绑定错误
    RpaPicker.bindError(() => {
      message.error(t('rpaPickerUnavailable'))
    })
  }

  /**
   * 开始拾取
   * @param type  类型 '' 普通拾取， ''similar' 相似度拾取, 'cv' cv拾取
   * @param element  元素数据， 相似度拾取时，element不能为空
   * @param callback 成功/失败回调
   * @param mode 可选，拾取可指定桌面/web等，仅原子能力配置中拾取
   */
  const startPick = (type: string, element: any, callback: (params: { success: boolean, data: any }) => void, mode = '') => {
    type = type.toUpperCase()
    isPicking.value = true
    // 深度捕获: 启用侧边实时树面板(引擎仅 DeepUIA 会话推送 pick_tree_update)
    const isDeepMode = mode === 'DeepUIA'
    if (isDeepMode)
      isDeepPicking.value = true
    // 启动拾取
    RpaPicker.create(() => {
      const _pickType = pickTypeMap[type] || 'ELEMENT'
      console.log('type: ', type)
      console.log('_pickType: ', _pickType)
      console.log('element: ', element)
      pickerType.value = _pickType
      const data = element ? JSON.stringify(element) : ''
      const ext_data = { global: variableStore.globalVariableList }
      setTimeout(() => {
        const sendParams: PickParams = {
          pick_sign: 'START',
          pick_type: _pickType,
          pick_mode: mode,
          data,
        }
        console.log('startPick sendParams: ', sendParams)
        if (_pickType === 'SIMILAR') { // 相似拾取 带上ext_data
          sendParams.ext_data = ext_data
        }
        RpaPicker.send(sendParams)
        if (isDeepMode)
          enterDeepSidebarMode()
        else
          windowManager.minimizeWindow()
      }, 500)
    })
    // 绑定消息
    RpaPicker.bindMessage((res) => {
      const { key, data, err_msg } = res || {} // key: 'success' | 'error' | 'ping' | 'pick_tree_update'
      // 深度捕获实时控件树增量推送: 仅更新面板数据, 不结束拾取
      if (key === 'pick_tree_update') {
        try {
          liveTreeData.value = data ? JSON.parse(data) : null
        }
        catch {}
        return
      }
      if (key === 'success' && data) {
        finishPick()
        const dataObj = JSON.parse(data)
        if (dataObj.app) {
          callback?.({ success: true, data: dataObj })
        }
      }
      if (key === 'error') {
        // 引擎侧自绘控件等场景返回带建议的中文错误文案, 直接透传展示(6s时长便于阅读建议)
        const errorMsg = data || err_msg || t('rpaPickerUnavailable')
        message.error(errorMsg, 6)
        finishPick()
      }
      if (key === 'cancel') {
        finishPick()
      }
    })
    // 绑定关闭
    RpaPicker.bindClose(() => {
      callback?.({
        success: false,
        data: null,
      })
      finishPick()
    })
    // 绑定错误
    RpaPicker.bindError(() => {
      message.error(t('rpaPickerUnavailable'))
    })
  }
  // 开始校验 validateMode: 校验模式(位置/点击/输入/悬浮), 见 config/pick.ts VALID_*
  const startCheck = (type: string, data: any, callback: (params: { success: boolean, data: any }) => void, finshType = 'maximize', validateMode = '') => {
    // console.log('startCheck: ', data)
    type = type.toUpperCase()
    isChecking.value = true
    const ext_data: Record<string, any> = { global: variableStore.globalVariableList }
    if (validateMode)
      ext_data.validate_mode = validateMode
    // 启动校验
    RpaPicker.create(() => {
      windowManager.minimizeWindow()
      setTimeout(() => {
        const _pickType = validTypeMap[type] || 'ELEMENT'
        RpaPicker.send({ pick_sign: 'VALIDATE', pick_type: _pickType, data, ext_data })
        isChecking.value = false // 校验时，不显示loading
      }, 500)
    })
    // 绑定消息
    RpaPicker.bindMessage((res) => {
      console.log('startCheck res: ', res)
      if (res && res.key === 'success') {
        callback && callback({
          success: true,
          data: res,
        })
      }
      else {
        const { data, err_msg } = res || {}
        const errorMsg = data || err_msg || t('rpaPickerUnavailable')
        message.error(errorMsg)
        callback?.({
          success: false,
          data: null,
        })
      }
      finishCheck(finshType)
    })
    // 绑定关闭
    RpaPicker.bindClose(() => {
      callback?.({
        success: false,
        data: null,
      })
      finishCheck(finshType)
    })
    // 绑定错误
    RpaPicker.bindError(() => {
      message.error(t('rpaPickerUnavailable'))
    })
  }

  // 重新拾取
  const repick = (type: string, isModal: boolean = false, group: string, callback?: () => void) => {
    startPick(type, '', (res) => {
      // console.log('repick res: ', res)
      if (res.success) {
        useElements.setTempElement(res.data, 'repick', group)
      }
      isModal && elementPickModal.show()
      callback && callback()
    })
  }
  // 相似拾取
  const similarPick = (element: any, callback?: () => void) => {
    startPick('SIMILAR', element, (res) => {
      console.log('similarPick res: ', res)
      if (res.success) {
        useElements.setTempElement(res.data, 'similar')
      }
      callback && callback()
    })
  }
  // 新建拾取
  const newPick = (type: string, callback?: () => void) => {
    startPick(type, '', (res) => {
      if (res.success) {
        useElements.setTempElement(res.data)
        elementPickModal.show({ isContinue: true })
      }
      callback?.()
    })
  }
  // 深度捕获新建拾取(对应影刀"深度模式"): 跳过策略试探直达 UIA 引擎,
  // 以更大遍历深度下钻, 用于标准模式选不中/选中范围过大的复杂桌面软件
  const newDeepPick = (callback?: () => void) => {
    startPick('', '', (res) => {
      if (res.success) {
        useElements.setTempElement(res.data)
        elementPickModal.show({ isContinue: true })
      }
      callback?.()
    }, 'DeepUIA')
  }

  // groupPick
  const groupPick = (type: string, group: string, callback?: () => void) => {
    startPick(type, '', (res) => {
      if (res.success) {
        useElements.setTempElement(res.data, 'new', group)
        elementPickModal.show()
        callback && callback()
      }
    })
  }
  // set isDataPicking
  const setDataPicking = (val: boolean) => {
    isDataPicking.value = val
    BUS.$once('batch-close', () => {
      isDataPicking.value = false
    })
  }

  // ---- E1 控件树浏览器 ----
  // 打开通道并导出桌面控件树(独立会话, 与拾取/校验互斥使用)
  const openControlTree = (callback: (params: { success: boolean, data: any }) => void) => {
    isTreeLoading.value = true
    RpaPicker.create(() => {
      setTimeout(() => {
        RpaPicker.send({ pick_sign: 'CONTROL_TREE', ext_data: { max_depth: 6 } })
      }, 500)
    })
    RpaPicker.bindMessage((res) => {
      isTreeLoading.value = false
      if (res && res.key === 'success') {
        try {
          callback({ success: true, data: res.data ? JSON.parse(res.data) : null })
        }
        catch {
          message.error(t('rpaPickerUnavailable'))
          callback({ success: false, data: null })
        }
      }
      else {
        const { data, err_msg } = res || {}
        message.error(data || err_msg || t('rpaPickerUnavailable'))
        callback({ success: false, data: null })
      }
    })
    RpaPicker.bindClose(() => {
      isTreeLoading.value = false
      callback({ success: false, data: null })
    })
    RpaPicker.bindError(() => {
      isTreeLoading.value = false
      message.error(t('rpaPickerUnavailable'))
    })
  }
  // 点选树节点高亮(后端按 rect 直接绘制, 无需重新定位)
  const highlightTreeNode = (rect: { left: number, top: number, right: number, bottom: number }) => {
    RpaPicker.bindMessage(() => {}) // 高亮响应无需消费
    RpaPicker.send({ pick_sign: 'CONTROL_TREE', ext_data: { rect } })
  }
  // 树节点点选拾取: 上报窗口层→目标层属性链, 后端构造元素并验证定位(复用树浏览器会话)
  const pickTreeNode = (chain: any[], callback: (params: { success: boolean, data: any }) => void) => {
    RpaPicker.bindMessage((res) => {
      if (res && res.key === 'success' && res.data) {
        try {
          const payload = JSON.parse(res.data)
          callback({ success: true, data: payload })
          return
        }
        catch {}
      }
      const { data, err_msg } = res || {}
      message.error(data || err_msg || t('rpaPickerUnavailable'))
      callback({ success: false, data: null })
    })
    RpaPicker.send({ pick_sign: 'CONTROL_TREE', ext_data: { pick: chain } })
  }
  // 关闭控件树浏览器会话
  const closeControlTree = () => {
    RpaPicker.destroy()
  }

  // ---- 批量校验(发布前体检, 独立会话) ----
  // items: [{id, name, element: 元素json串}], 回调返回逐项报告 [{id, name, success, note|error}]
  const batchValidate = (items: any[], callback: (params: { success: boolean, data: any }) => void) => {
    isChecking.value = true
    RpaPicker.create(() => {
      setTimeout(() => {
        RpaPicker.send({ pick_sign: 'BATCH_VALIDATE', data: JSON.stringify(items) })
      }, 500)
    })
    RpaPicker.bindMessage((res) => {
      isChecking.value = false
      if (res && res.key === 'success' && res.data) {
        try {
          callback({ success: true, data: JSON.parse(res.data) })
        }
        catch {
          callback({ success: false, data: null })
        }
      }
      else {
        const { data, err_msg } = res || {}
        message.error(data || err_msg || t('rpaPickerUnavailable'))
        callback({ success: false, data: null })
      }
      RpaPicker.destroy()
    })
    RpaPicker.bindClose(() => {
      isChecking.value = false
      callback({ success: false, data: null })
    })
    RpaPicker.bindError(() => {
      isChecking.value = false
      message.error(t('rpaPickerUnavailable'))
    })
  }

  // ---- 定位指标面板(I2 可观测性, 独立会话) ----
  // 回调返回 { metrics: 计数指标, heal_cache: { 缓存键: 条目 } }
  const pickerMetrics = (callback: (params: { success: boolean, data: any }) => void) => {
    RpaPicker.create(() => {
      setTimeout(() => {
        RpaPicker.send({ pick_sign: 'PICKER_METRICS' })
      }, 500)
    })
    RpaPicker.bindMessage((res) => {
      if (res && res.key === 'success' && res.data) {
        try {
          callback({ success: true, data: JSON.parse(res.data) })
        }
        catch {
          callback({ success: false, data: null })
        }
      }
      else {
        const { data, err_msg } = res || {}
        message.error(data || err_msg || t('rpaPickerUnavailable'))
        callback({ success: false, data: null })
      }
      RpaPicker.destroy()
    })
    RpaPicker.bindClose(() => {
      callback({ success: false, data: null })
    })
    RpaPicker.bindError(() => {
      message.error(t('rpaPickerUnavailable'))
    })
  }

  // 删除单条自愈缓存(指标面板手动清理, key 为缓存键), 回调返回 { key, dropped }
  const healCacheDrop = (key: string, callback: (params: { success: boolean, data: any }) => void) => {
    RpaPicker.create(() => {
      setTimeout(() => {
        RpaPicker.send({ pick_sign: 'HEAL_CACHE_DROP', data: key })
      }, 500)
    })
    RpaPicker.bindMessage((res) => {
      if (res && res.key === 'success' && res.data) {
        try {
          callback({ success: true, data: JSON.parse(res.data) })
        }
        catch {
          callback({ success: false, data: null })
        }
      }
      else {
        const { data, err_msg } = res || {}
        message.error(data || err_msg || t('rpaPickerUnavailable'))
        callback({ success: false, data: null })
      }
      RpaPicker.destroy()
    })
    RpaPicker.bindClose(() => {
      callback({ success: false, data: null })
    })
    RpaPicker.bindError(() => {
      message.error(t('rpaPickerUnavailable'))
    })
  }

  // I1: CV 歧义交互式消歧(用户选定候选后按坐标校验, 一次性决策不写自愈缓存)
  // item: {id, name, rect: [l,t,r,b], score}, 回调返回 {id, name, success, rect, center, score}
  const cvDisambiguate = (item: any, callback: (params: { success: boolean, data: any }) => void) => {
    RpaPicker.create(() => {
      setTimeout(() => {
        RpaPicker.send({ pick_sign: 'CV_DISAMBIGUATE', data: JSON.stringify(item) })
      }, 500)
    })
    RpaPicker.bindMessage((res) => {
      if (res && res.key === 'success' && res.data) {
        try {
          callback({ success: true, data: JSON.parse(res.data) })
        }
        catch {
          callback({ success: false, data: null })
        }
      }
      else {
        const { data, err_msg } = res || {}
        message.error(data || err_msg || t('rpaPickerUnavailable'))
        callback({ success: false, data: null })
      }
      RpaPicker.destroy()
    })
    RpaPicker.bindClose(() => {
      callback({ success: false, data: null })
    })
    RpaPicker.bindError(() => {
      message.error(t('rpaPickerUnavailable'))
    })
  }

  watch(isDataPicking, (val) => {
    if (val) {
      $loading.open({ msg: '正在抓取，无法操作客户端', timeout: 100 * 60 })
    }
    else {
      $loading.close()
    }
  })

  return {
    isPicking,
    isChecking,
    isDataPicking,
    isTreeLoading,
    isDeepPicking,
    liveTreeData,
    startMousePick,
    startPick,
    startCheck,
    repick,
    similarPick,
    newPick,
    newDeepPick,
    groupPick,
    setDataPicking,
    openControlTree,
    highlightTreeNode,
    pickTreeNode,
    closeControlTree,
    batchValidate,
    pickerMetrics,
    healCacheDrop,
    cvDisambiguate,
  }
})
