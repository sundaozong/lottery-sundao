<template>
  <teleport to="body">
    <!-- Toast 栈 -->
    <div class="toast-stack" role="status" aria-live="polite">
      <div
        v-for="t in state.toasts"
        :key="t.id"
        class="toast-item"
        :class="t.type"
      >
        <AppIcon v-if="t.type === 'ok'" name="checkCircle" />
        <AppIcon v-else-if="t.type === 'error'" name="alert" />
        <AppIcon v-else name="info" />
        <span class="toast-msg">{{ t.message }}</span>
        <button
          type="button"
          class="toast-close"
          aria-label="关闭提示"
          @click="dismissToast(t.id)"
        >×</button>
      </div>
    </div>

    <!-- 确认对话框 -->
    <div
      v-if="state.confirm"
      class="modal-mask"
      @click.self="cancel"
      role="dialog"
      aria-modal="true"
      :aria-label="state.confirm.title"
    >
      <div class="modal-card" @keydown.esc.stop="cancel">
        <div class="modal-title">{{ state.confirm.title }}</div>
        <div class="modal-body">{{ state.confirm.message }}</div>
        <div class="modal-actions">
          <button ref="cancelBtn" type="button" class="btn btn-ghost" @click="cancel">
            {{ state.confirm.cancelText }}
          </button>
          <button
            ref="confirmBtn"
            type="button"
            class="btn"
            :class="state.confirm.danger ? 'btn-danger' : 'btn-primary'"
            @click="confirm"
          >
            {{ state.confirm.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { useFeedback, dismissToast, resolveConfirm } from '../composables/feedback'

const state = useFeedback()
const cancelBtn = ref(null)
const confirmBtn = ref(null)

function confirm() {
  resolveConfirm(true)
}
function cancel() {
  resolveConfirm(false)
}

watch(
  () => state.confirm,
  async (dialog) => {
    if (!dialog) return
    await nextTick()
    // 危险操作默认聚焦「取消」，防误删
    ;(dialog.danger ? cancelBtn.value : confirmBtn.value)?.focus()
  },
)
</script>
