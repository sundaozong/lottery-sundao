import { reactive } from 'vue'

let seq = 0

const state = reactive({
  toasts: [],
  confirm: null,
})

let confirmResolver = null

/**
 * 轻提示
 * @param {string} message
 * @param {'ok'|'error'|'info'} type
 * @param {number} duration
 */
export function toast(message, type = 'info', duration = 2600) {
  const id = ++seq
  state.toasts.push({ id, message, type, leaving: false })
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration)
  }
  return id
}

export function dismissToast(id) {
  const item = state.toasts.find((t) => t.id === id)
  if (!item || item.leaving) return
  item.leaving = true
  setTimeout(() => {
    const idx = state.toasts.findIndex((t) => t.id === id)
    if (idx >= 0) state.toasts.splice(idx, 1)
  }, 160)
}

/**
 * 确认对话框（Promise 化，替代 window.confirm）
 * @param {{ title?: string, message: string, confirmText?: string, cancelText?: string, danger?: boolean }} options
 * @returns {Promise<boolean>}
 */
export function confirmDialog(options = {}) {
  if (state.confirm && confirmResolver) {
    confirmResolver(false)
    confirmResolver = null
  }
  state.confirm = {
    title: options.title || '请确认',
    message: options.message || '',
    confirmText: options.confirmText || '确认',
    cancelText: options.cancelText || '取消',
    danger: options.danger !== false,
  }
  return new Promise((resolve) => {
    confirmResolver = resolve
  })
}

export function resolveConfirm(value) {
  state.confirm = null
  if (confirmResolver) {
    confirmResolver(value)
    confirmResolver = null
  }
}

export function useFeedback() {
  return state
}
