/**
 * 页面可见时才执行的轮询定时器
 *
 * 窗口最小化/切换到后台时自动暂停轮询(document.visibilityState),
 * 回到前台立即补一次执行并恢复轮询, 避免后台持续请求调度器/后端。
 *
 * @param fn 轮询回调
 * @param ms 轮询间隔(毫秒)
 * @returns stop 停止函数(组件卸载时调用)
 */
export function setIntervalWhenVisible(fn: () => void, ms: number) {
  let timer: ReturnType<typeof setInterval> | null = null

  const start = () => {
    if (timer === null && document.visibilityState === 'visible')
      timer = setInterval(fn, ms)
  }

  const stop = () => {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  const onVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      // 回到前台: 立即补一次 + 恢复轮询(后台期间可能错过多次刷新)
      fn()
      start()
    }
    else {
      stop()
    }
  }

  document.addEventListener('visibilitychange', onVisibilityChange)
  start()

  return () => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    stop()
  }
}
