import { log } from '../3rd/log'
import { ErrorMessage, StatusCode } from '../common/constant'
import { Utils } from '../common/utils'

import { Tabs } from './tab'

/**
 * Dialog auto-handling state (persisted across bgHandler calls)
 */
const dialogState = {
  enabled: false,
  accept: true,
  promptText: '',
}

let navigationListenerRegistered = false

/**
 * Injected into page MAIN world: override alert/confirm/prompt.
 * Native references are kept so we can restore later.
 */
function astronDialogOverride(cfg: { accept: boolean, promptText: string }) {
  const w = window as any
  if (!w.__astronNativeAlert__) {
    w.__astronNativeAlert__ = window.alert
    w.__astronNativeConfirm__ = window.confirm
    w.__astronNativePrompt__ = window.prompt
  }
  if (!Array.isArray(w.__astronDialogs__)) {
    w.__astronDialogs__ = []
  }
  w.__astronDialogCfg__ = cfg
  window.alert = function (message?: any) {
    w.__astronDialogs__.push({ type: 'alert', message: String(message ?? ''), time: Date.now() })
  }
  window.confirm = function (message?: any) {
    w.__astronDialogs__.push({ type: 'confirm', message: String(message ?? ''), time: Date.now() })
    return cfg.accept !== false
  }
  window.prompt = function (message?: any, defaultValue?: string) {
    w.__astronDialogs__.push({ type: 'prompt', message: String(message ?? ''), time: Date.now() })
    if (cfg.promptText) {
      return cfg.promptText
    }
    return typeof defaultValue === 'undefined' ? null : defaultValue
  }
}

/**
 * Injected into page MAIN world: restore native dialog functions.
 */
function astronDialogRestore() {
  const w = window as any
  if (w.__astronNativeAlert__) {
    window.alert = w.__astronNativeAlert__
    window.confirm = w.__astronNativeConfirm__
    window.prompt = w.__astronNativePrompt__
  }
  w.__astronDialogCfg__ = null
}

/**
 * Injected into page MAIN world: collect recorded dialogs.
 */
function astronDialogCollect(clear: boolean) {
  const w = window as any
  const dialogs = Array.isArray(w.__astronDialogs__) ? w.__astronDialogs__ : []
  if (clear) {
    w.__astronDialogs__ = []
  }
  return dialogs
}

async function injectIntoTab(tabId: number, args: any[], func: (...fnArgs: any[]) => any) {
  await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    world: 'MAIN',
    func,
    args,
  } as any)
}

function registerNavigationListener() {
  if (navigationListenerRegistered) {
    return
  }
  navigationListenerRegistered = true
  chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
    if (dialogState.enabled && changeInfo.status === 'loading') {
      // Re-inject after each navigation so the override keeps working
      chrome.tabs.query({}, (tabs) => {
        for (const tab of tabs) {
          if (!Utils.isSupportProtocal(tab.url)) {
            continue
          }
          injectIntoTab(tab.id, [{ accept: dialogState.accept, promptText: dialogState.promptText }], astronDialogOverride).catch(() => {
            // Ignore frames that cannot be injected
          })
        }
      })
    }
  })
}

export const DialogHandler = {
  /**
   * Enable/disable automatic dialog handling.
   * params.data: { enable: boolean, button?: 'ok' | 'cancel', promptText?: string }
   */
  async setDialogAuto(params: { data: { enable?: boolean, button?: string, promptText?: string } }) {
    const { enable, button, promptText } = params.data || {}
    const tab = await Tabs.getActiveTab()
    if (!tab) {
      return Utils.fail(ErrorMessage.ACTIVE_TAB_ERROR)
    }
    try {
      if (enable) {
        dialogState.enabled = true
        dialogState.accept = button !== 'cancel'
        dialogState.promptText = promptText || ''
        registerNavigationListener()
        await injectIntoTab(tab.id, [{ accept: dialogState.accept, promptText: dialogState.promptText }], astronDialogOverride)
        log.info('Dialog auto handler enabled')
        return Utils.success(true)
      }
      else {
        dialogState.enabled = false
        await injectIntoTab(tab.id, [], astronDialogRestore)
        log.info('Dialog auto handler disabled')
        return Utils.success(false)
      }
    }
    catch (error) {
      return Utils.fail(error.toString(), StatusCode.EXECUTE_ERROR)
    }
  },

  /**
   * Collect recorded dialog messages.
   * params.data: { clear?: boolean }
   */
  async getDialogText(params: { data: { clear?: boolean } }) {
    const tab = await Tabs.getActiveTab()
    if (!tab) {
      return Utils.fail(ErrorMessage.ACTIVE_TAB_ERROR)
    }
    try {
      const clear = params.data ? params.data.clear !== false : true
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: 'MAIN',
        func: astronDialogCollect,
        args: [clear],
      } as any)
      const dialogs = results && results[0] && results[0].result ? results[0].result : []
      return Utils.success(dialogs)
    }
    catch (error) {
      return Utils.fail(error.toString(), StatusCode.EXECUTE_ERROR)
    }
  },
}
