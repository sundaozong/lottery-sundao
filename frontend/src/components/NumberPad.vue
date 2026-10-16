<template>
  <div class="picker">
    <div class="picker-head">
      <span class="form-hint">{{ status }}</span>
      <button v-if="selected.length" class="text-btn" type="button" @click="emit('update:selected', [])">清空</button>
    </div>
    <div class="num-pad" :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }">
      <button
        v-for="n in numbers"
        :key="n"
        type="button"
        class="num-cell"
        :class="[color, { on: countOf(n) > 0, locked: blocked(n) }]"
        :aria-pressed="countOf(n) > 0"
        @click="pick(n)"
      >
        {{ textOf(n) }}
        <i v-if="countOf(n) > 1">{{ countOf(n) }}</i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  from: { type: Number, required: true },
  to: { type: Number, required: true },
  pad: { type: Number, default: 1 },
  color: { type: String, default: 'green' },
  selected: { type: Array, default: () => [] },
  max: { type: Number, default: 0 },
  maxPer: { type: Number, default: 1 },
  min: { type: Number, default: 0 },
})
const emit = defineEmits(['update:selected'])

const numbers = computed(() => {
  const list = []
  for (let n = props.from; n <= props.to; n += 1) list.push(n)
  return list
})
const cols = computed(() => (numbers.value.length <= 12 ? numbers.value.length : 10))
const status = computed(() => {
  const count = props.selected.length
  if (props.max > 0 && props.min > 0 && props.min !== props.max) return `已选 ${count} 个，至少 ${props.min}，最多 ${props.max}`
  if (props.max > 0) return `已选 ${count} / ${props.max}`
  if (props.min > 0) return `已选 ${count} 个，至少 ${props.min}`
  return `已选 ${count} 个`
})

function textOf(n) {
  return props.pad > 1 ? String(n).padStart(props.pad, '0') : String(n)
}

function countOf(n) {
  const token = textOf(n)
  return props.selected.filter((item) => item === token).length
}

function blocked(n) {
  if (countOf(n) > 0) return false
  if (props.max > 0 && props.selected.length >= props.max) return true
  return false
}

function pick(n) {
  const token = textOf(n)
  const count = countOf(n)
  if (props.max === 1 && props.maxPer === 1) {
    emit('update:selected', count ? [] : [token])
    return
  }
  if (count > 0) {
    if (count < props.maxPer && (props.max <= 0 || props.selected.length < props.max)) {
      emit('update:selected', sortTokens([...props.selected, token]))
      return
    }
    const next = props.selected.slice()
    next.splice(next.lastIndexOf(token), 1)
    emit('update:selected', next)
    return
  }
  if (props.max > 0 && props.selected.length >= props.max) return
  emit('update:selected', sortTokens([...props.selected, token]))
}

function sortTokens(list) {
  return list.slice().sort((a, b) => Number(a) - Number(b) || String(a).localeCompare(String(b)))
}
</script>
