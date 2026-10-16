<template>
  <div class="balls">
    <template v-if="positionGroups.length">
      <span v-for="(group, i) in positionGroups" :key="'p' + i" class="pos-group">
        <span class="pos-label">{{ group.label }}</span>
        <component
          :is="interactive ? 'button' : 'span'"
          v-for="(n, j) in group.nums"
          :key="j"
          class="ball"
          :class="[group.kind, size, markClass(positionFlags(i), j), interactive ? 'pick' : '']"
          :type="interactive ? 'button' : undefined"
          :title="markTitle(positionFlags(i), j)"
          @click="onPick(n)"
        >{{ n }}</component>
      </span>
    </template>
    <template v-else>
      <component
        :is="interactive ? 'button' : 'span'"
        v-for="(n, i) in numbers.main || []"
        :key="'m' + i"
        class="ball"
        :class="[mainClass, size, markClass(marks && marks.main, i), interactive ? 'pick' : '']"
        :type="interactive ? 'button' : undefined"
        :title="markTitle(marks && marks.main, i)"
        @click="onPick(n)"
      >{{ n }}</component>
      <template v-if="(numbers.special || []).length">
        <span class="plus">+</span>
        <component
          :is="interactive ? 'button' : 'span'"
          v-for="(n, i) in numbers.special"
          :key="'s' + i"
          class="ball"
          :class="[specialClass, size, markClass(marks && marks.special, i), interactive ? 'pick' : '']"
          :type="interactive ? 'button' : undefined"
          :title="markTitle(marks && marks.special, i)"
          @click="onPick(n)"
        >{{ n }}</component>
      </template>
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
  interactive: { type: Boolean, default: false },
})

const emit = defineEmits(['pick'])

function onPick(n) {
  if (!props.interactive) return
  emit('pick', n)
}

const POS_LABELS = {
  fc3d: ['百', '十', '个'],
  pl3: ['百', '十', '个'],
  pl5: ['万', '千', '百', '十', '个'],
  qxc: ['1', '2', '3', '4', '5', '6', '特'],
}

const mainClass = computed(() => ballClass(props.type, 'main'))
const specialClass = computed(() => ballClass(props.type, 'special'))
const positionGroups = computed(() => {
  const positions = props.numbers?.positions || []
  if (!positions.some((pos) => (pos || []).length)) return []
  const labels = POS_LABELS[props.type] || positions.map((_, i) => String(i + 1))
  return positions.map((nums, i) => ({
    label: labels[i] || String(i + 1),
    nums: nums || [],
    kind: props.type === 'qxc' && i === positions.length - 1 ? specialClass.value : mainClass.value,
  }))
})

function positionFlags(i) {
  return props.marks?.positions?.[i] || null
}

function markClass(flags, i) {
  if (!flags || flags[i] == null) return ''
  return flags[i] ? 'hit' : 'miss'
}

function markTitle(flags, i) {
  if (!flags || flags[i] == null) return undefined
  return flags[i] ? '命中' : '未中'
}
</script>
