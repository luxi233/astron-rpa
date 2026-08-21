import { ASTRON_SW_NAME } from '../common/constant'

function isExtensionContextValid() {
  try {
    return !!(chrome.runtime && chrome.runtime.id)
  }
  catch (error) {
    console.error('Error checking extension context:', error)
    return false
  }
}
function sendToBackground(message) {
  return new Promise((resolve, reject) => {
    if (!isExtensionContextValid()) {
      // 扩展上下文失效时 reject 而非把错误字符串当正常数据 resolve,
      // 避免下游(如拾取链路)把 'Extension context is not valid' 当元素数据处理
      reject(new Error('Extension context is not valid'))
      return
    }
    try {
      chrome.runtime.sendMessage(message, (response) => {
        resolve(response)
      })
    }
    catch (error) {
      reject(error)
    }
  })
}

export function sendElementData(elementData) {
  sendToBackground({
    type: 'element',
    data: elementData,
  }).catch(error => console.warn('sendElementData failed:', error))
}

export function requestFrame() {
  return sendToBackground({
    type: 'requestFrameId',
  })
}

export function keepServiceWorkerAlive() {
  // 运行上下文无扩展 runtime(测试环境/非扩展页面)时跳过保活连接;
  // 生产 content script 恒有 runtime, 上下文失效走 onDisconnect 重试链路
  if (!chrome?.runtime?.connect || !chrome.runtime.id)
    return
  const port = chrome.runtime.connect(chrome.runtime.id, { name: ASTRON_SW_NAME })
  port.onDisconnect.addListener(() => {
    sendToBackground({ type: 'keepServiceWorkerAlive' })
      .then(() => {
        keepServiceWorkerAlive()
      })
      .catch(() => {
        // 上下文失效时延迟重试, 避免热循环
        setTimeout(keepServiceWorkerAlive, 1000)
      })
  })
}

export function notifyContentLoaded() {
  return sendToBackground({
    type: 'contentLoaded',
  }).catch(error => console.warn('notifyContentLoaded failed:', error))
}
