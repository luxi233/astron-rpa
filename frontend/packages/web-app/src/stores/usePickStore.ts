import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { Ref } from 'vue'

import { baseUrl } from '@/utils/env'
import BUS from '@/utils/eventBus'
import $loading from '@/utils/globalLoading'

import { RpaPicker } from '@/api/pick'
import { WINDOW_NAME } from '@/constants'
import { DEEP_PICK_EVENT, DEEP_PICK_HEIGHT, DEEP_PICK_WIDTH } from '@/constants/deepPick'
import { utilsManager, windowManager } from '@/platform'
import type { CreateWindowOptions } from '@/platform'
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
  // 深度捕获实时控件树: 捕获进行中弹出独立面板窗口(影刀式), 主窗口保持最小化不做几何变形,
  // 随鼠标推送增量树经 w2w 转发至面板展示(拾取会话/WS 仍在主窗口)
  const isDeepPicking = ref(false)
  const liveTreeData = ref<any>(null)
  // 深度捕获回调引用: 面板窗口关闭取消时, 监听器无法触及 startPick 闭包内的 callback, 暂存于此统一回调;
  // deepPickWinId 用于识别主进程 window-close 事件对应的正是面板窗口(孤儿面板兜底取消)
  let deepPickCallback: ((params: { success: boolean, data: any }) => void) | null = null
  let deepPickWinId: number | string | null = null

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
  // 深度捕获面板窗口: 独立窗口承载实时树, 替代旧的"主窗口收缩为侧边栏"方案——
  // 主窗口 RouterView 不再被替换卸载, 彻底消除 Arrange onUnmounted 误杀拾取三件套的问题;
  // 同时免去主窗口 restore/setPosition/setWindowSize 几何体操(最大化时 setBounds 静默失效等坑)
  async function openDeepPickWindow() {
    if (isDeepPicking.value)
      return
    isDeepPicking.value = true
    const options: CreateWindowOptions = {
      url: `${baseUrl}/deeppick.html`,
      label: WINDOW_NAME.DEEP_PICK,
      title: '深度捕获',
      position: 'right_center',
      width: DEEP_PICK_WIDTH,
      height: DEEP_PICK_HEIGHT,
      resizable: true,
      decorations: false,
      transparent: true,
      skipTaskbar: true,
      alwaysOnTop: true,
    }
    deepPickWinId = await windowManager.createWindow(options)
  }

  // 主窗口 → 面板窗口: 转发实时树(传已解析对象, w2w 自带 JSON 序列化)
  function emitToDeepPickWindow(type: DEEP_PICK_EVENT, data: any = '') {
    windowManager.emitTo({
      type,
      target: WINDOW_NAME.DEEP_PICK,
      from: WINDOW_NAME.MAIN,
      data,
    })
  }

  // 面板窗口 → 主窗口: 关闭面板即取消捕获; 树节点点选则经拾取会话发给引擎(拾取进行中才响应, 常驻监听无需解绑)
  utilsManager.listenEvent('w2w', ({ from, target, type, data }: { from: string, target: string, type: string, data?: any }) => {
    if (from !== WINDOW_NAME.DEEP_PICK || target !== WINDOW_NAME.MAIN)
      return
    if (!isPicking.value)
      return
    if (type === DEEP_PICK_EVENT.CANCEL) {
      deepPickCallback?.({ success: false, data: null })
      finishPick()
    }
    else if (type === DEEP_PICK_EVENT.TREE_PICK && Array.isArray(data) && data.length) {
      // 树节点点选捕获: 属性链随 TREE_PICK sign 发给引擎, 定位成功后引擎以捕获成功结束会话(走下方 success 主路径)
      RpaPicker.send({ pick_sign: 'TREE_PICK', data: JSON.stringify(data) })
    }
  })

  // 兜底: 面板被直接关闭(如 Alt+F4/任务栏关闭, CANCEL 的 w2w 可能来不及送达)时, 主进程 close 事件仍会经 window-close 到达;
  // 与 CANCEL 路径靠 isPicking 守卫互斥幂等(先到者 finishPick 置 false, 后到者直接忽略)
  utilsManager.listenEvent('window-close', (id: number | string) => {
    if (deepPickWinId === null || id !== deepPickWinId || !isPicking.value)
      return
    deepPickCallback?.({ success: false, data: null })
    finishPick()
  })

  // 拾取结束
  function finishPick() {
    isPicking.value = false
    isDeepPicking.value = false
    liveTreeData.value = null
    deepPickCallback = null
    deepPickWinId = null
    RpaPicker.destroy()
    // 深度捕获面板窗口收尾: 先发 FINISH 通知自毁, 再按 label 关闭兜底(窗口可能已被用户手动关闭, closeWindow 对缺失 label 无害)
    emitToDeepPickWindow(DEEP_PICK_EVENT.FINISH)
    windowManager.closeWindow(WINDOW_NAME.DEEP_PICK)
    windowManager.setWindowAlwaysOnTop(false)
    windowManager.maximizeWindow(true)
  }
  // 校验结束
  function finishCheck(finshType = 'maximize') {
    isChecking.value = false
    RpaPicker.destroy()
    finshType === 'maximize' ? windowManager.maximizeWindow(true) : windowManager.restoreWindow()
  }
  // 一次性拾取会话: 统一 create→send→bind 四件套样板(控件树浏览器/批量校验/指标/自愈清理/CV 消歧共用);
  // keepSession 为 true 时结束不销毁 WS(控件树浏览器后续高亮/点选复用同一连接)
  function pickerSession(
    sendParams: object,
    callback: (params: { success: boolean, data: any }) => void,
    options: { keepSession?: boolean, loadingRef?: Ref<boolean> } = {},
  ) {
    const { keepSession = false, loadingRef } = options
    const setLoading = (v: boolean) => {
      if (loadingRef)
        loadingRef.value = v
    }
    setLoading(true)
    RpaPicker.create(() => {
      setTimeout(() => {
        RpaPicker.send(sendParams)
      }, 500)
    })
    RpaPicker.bindMessage((res) => {
      setLoading(false)
      if (res && res.key === 'success' && res.data) {
        try {
          callback({ success: true, data: JSON.parse(res.data) })
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
      if (!keepSession)
        RpaPicker.destroy()
    })
    RpaPicker.bindClose(() => {
      setLoading(false)
      callback({ success: false, data: null })
    })
    RpaPicker.bindError(() => {
      setLoading(false)
      message.error(t('rpaPickerUnavailable'))
    })
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
    // 深度捕获: 实时树展示在独立面板窗口(引擎仅 DeepUIA 会话推送 pick_tree_update)
    const isDeepMode = mode === 'DeepUIA'
    if (isDeepMode)
      deepPickCallback = callback
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
          openDeepPickWindow()
        // 主窗口统一最小化(与标准拾取一致), 深度捕获的实时树由独立面板窗口承载
      }, 500)
    })
    // 绑定消息
    RpaPicker.bindMessage((res) => {
      const { key, data, err_msg } = res || {} // key: 'success' | 'error' | 'ping' | 'pick_tree_update'
      // 深度捕获实时控件树增量推送: 仅更新面板数据, 不结束拾取; 同步转发至独立面板窗口展示
      if (key === 'pick_tree_update') {
        try {
          const parsed = data ? JSON.parse(data) : null
          liveTreeData.value = parsed
          if (isDeepPicking.value)
            emitToDeepPickWindow(DEEP_PICK_EVENT.TREE_UPDATE, parsed)
        }
        catch {}
        return
      }
      if (key === 'success' && data) {
        const dataObj = JSON.parse(data)
        if (dataObj.tree_pick) {
          // 树节点点选 ack: 非捕获结果, 不结束会话; 定位失败提示换节点重试(成功则由主循环捕获结果到达)
          if (!dataObj.located)
            message.warning(t('deepCaptureTreePickNotFound'))
          return
        }
        finishPick()
        if (dataObj.app) {
          callback?.({ success: true, data: dataObj })
        }
        else {
          // 成功但元素数据不完整: 显式回调失败, 避免调用方(如表单拾取) loading 挂死
          callback?.({ success: false, data: null })
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
  // 打开通道并导出桌面控件树(独立会话, 与拾取/校验互斥使用; keepSession 保留连接供后续高亮/点选)
  const openControlTree = (callback: (params: { success: boolean, data: any }) => void) => {
    pickerSession({ pick_sign: 'CONTROL_TREE', ext_data: { max_depth: 6 } }, callback, { keepSession: true, loadingRef: isTreeLoading })
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
    pickerSession({ pick_sign: 'BATCH_VALIDATE', data: JSON.stringify(items) }, callback, { loadingRef: isChecking })
  }

  // ---- 定位指标面板(I2 可观测性, 独立会话) ----
  // 回调返回 { metrics: 计数指标, heal_cache: { 缓存键: 条目 } }
  const pickerMetrics = (callback: (params: { success: boolean, data: any }) => void) => {
    pickerSession({ pick_sign: 'PICKER_METRICS' }, callback)
  }

  // 删除单条自愈缓存(指标面板手动清理, key 为缓存键), 回调返回 { key, dropped }
  const healCacheDrop = (key: string, callback: (params: { success: boolean, data: any }) => void) => {
    pickerSession({ pick_sign: 'HEAL_CACHE_DROP', data: key }, callback)
  }

  // I1: CV 歧义交互式消歧(用户选定候选后按坐标校验, 一次性决策不写自愈缓存)
  // item: {id, name, rect: [l,t,r,b], score}, 回调返回 {id, name, success, rect, center, score}
  const cvDisambiguate = (item: any, callback: (params: { success: boolean, data: any }) => void) => {
    pickerSession({ pick_sign: 'CV_DISAMBIGUATE', data: JSON.stringify(item) }, callback)
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
