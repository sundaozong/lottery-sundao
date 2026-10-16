<template>
  <div class="balls">
    <span
      v-for="(n, i) in numbers.main || []"
      :key="'m' + i"
      class="ball"
      :class="[mainClass, size, markClass(marks && marks.main, i)]"
      :title="markTitle(marks && marks.main, i)"
    >{{ n }}</span>
    <template v-if="(numbers.special || []).length">
      <span class="plus">+</span>
      <span
        v-for="(n, i) in numbers.special"
        :key="'s' + i"
        class="ball"
        :class="[specialClass, size, markClass(marks && marks.special, i)]"
        :title="markTitle(marks && marks.special, i)"
      >{{ n }}</span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ballClass } from '../api'

const props = defineProps({
  numbers: { type: Object, default: () => ({ main: [], special: [] }) },
  type: { type: String, default: 'ssq' },
  size: { type: String, default: '' },
  marks: { type: Object, default: null },
})

const mainClass = computed(() => ballClass(props.type, 'main'))
const specialClass = computed(() => ballClass(props.type, 'special'))

function markClass(flags, i) {
  if (!flags || flags[i] == null) return ''
  return flags[i] ? 'hit' : 'miss'
}

function markTitle(flags, i) {
  if (!flags || flags[i] == null) return undefined
  return flags[i] ? '命中' : '未中'
}
</script>
