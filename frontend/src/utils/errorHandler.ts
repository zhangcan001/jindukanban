/**
 * 全局错误处理 —— 把"组件 setup/render 抛错"、"Promise unhandledrejection"、"普通 onerror"
 * 都集中拦下来,统一弹 ElMessage,避免页面静默白屏或者控制台报错但用户毫无感知。
 *
 * 设计原则:
 * - 所有错误归一成 { title, message } 后调用 ElMessage.error 展示——而不是直接把 Error 对象
 *   或 stack 丢到 UI 上(会泄露内部信息且丑陋)
 * - 同样的错误消息在 3 秒内重复触发只展示一次(节流),避免循环错误把屏幕铺满 toast
 * - 在 dev 环境保留 console.error,prod 不打——通过 import.meta.env.DEV 区分
 */
import { ElMessage } from 'element-plus'
import type { App } from 'vue'

import { ApiError } from '../api/http'

const recentErrors = new Map<string, number>()
const RATE_LIMIT_MS = 3_000

function shouldShow(message: string): boolean {
  const now = Date.now()
  const previous = recentErrors.get(message)
  if (previous !== undefined && now - previous < RATE_LIMIT_MS) {
    return false
  }
  recentErrors.set(message, now)
  // 清理过期条目,避免 Map 膨胀
  if (recentErrors.size > 50) {
    for (const [key, ts] of recentErrors) {
      if (now - ts > RATE_LIMIT_MS) {
        recentErrors.delete(key)
      }
    }
  }
  return true
}

function extractMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message || '页面发生异常,请刷新后重试。'
  }
  if (typeof error === 'string') {
    return error
  }
  return '页面发生未知异常,请刷新后重试。'
}

export function reportError(error: unknown, context?: string): void {
  const message = extractMessage(error)
  if (import.meta.env.DEV) {
    // dev 时保留完整堆栈方便排查
    // eslint-disable-next-line no-console
    console.error('[errorHandler]', context ?? '', error)
  }
  if (!shouldShow(message)) {
    return
  }
  ElMessage.error({
    message,
    duration: 4_000,
    showClose: true,
  })
}

export function installGlobalErrorHandler(app: App): void {
  app.config.errorHandler = (error, _instance, info) => {
    reportError(error, `vue:${info}`)
  }

  // Promise 没 catch 的拒绝
  window.addEventListener('unhandledrejection', event => {
    reportError(event.reason, 'unhandledrejection')
    // 不阻止默认行为——dev 时让浏览器控制台依然能看到
  })

  // 同步异常(setTimeout 抛错等)
  window.addEventListener('error', event => {
    // 资源加载错误(img/script onerror)走的也是这个事件,但 event.error 为 null,过滤掉
    if (event.error) {
      reportError(event.error, 'window.onerror')
    }
  })
}
