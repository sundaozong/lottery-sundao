<template>
  <div class="trend">
    <div class="trend-toolbar">
      <div class="chip-row compact">
        <button
          v-for="n in periodOptions"
          :key="n"
          type="button"
          class="chip"
          :class="{ active: periods === n }"
          @click="$emit('update:periods', n)"
        >近 {{ n }} 期</button>
      </div>
      <div class="trend-legend">
        <span class="ball xs" :class="mainBallClass">红</span> 开出
        <span class="ball xs" :class="specialBallClass">蓝</span> 特别号
        <span class="trend-omit-sample heat-3" title="当前窗口里越久未出，颜色越暖">12</span> 遗漏
      </div>
    </div>

    <div v-if="rows.length" class="trend-draft">
      <div class="trend-draft-picks">
        <template v-if="rule?.mode === 'digit'">
          <span v-for="(label, i) in rule.positions" :key="label" class="trend-slot">
            <span class="pos-label">{{ label }}</span>
            <button
              v-if="draft.main[i]"
              type="button"
              class="ball xs"
              :class="mainBallClass"
              :title="'移出' + label"
              @click="dropAt('main', i)"
            >{{ draft.main[i] }}</button>
            <span v-else class="trend-slot-empty">·</span>
          </span>
          <template v-if="rule.specMax">
            <span class="plus">+</span>
            <span class="trend-slot">
              <span class="pos-label">{{ rule.specialLabel }}</span>
              <button
                v-if="draft.special[0]"
                type="button"
                class="ball xs"
                :class="specialBallClass"
                :title="'移出' + rule.specialLabel"
                @click="dropAt('special', 0)"
              >{{ draft.special[0] }}</button>
              <span v-else class="trend-slot-empty">·</span>
            </span>
          </template>
        </template>
        <template v-else>
          <button
            v-for="(n, i) in draft.main"
            :key="'dm' + n + i"
            type="button"
            class="ball xs"
            :class="mainBallClass"
            title="移出"
            @click="dropAt('main', i)"
          >{{ n }}</button>
          <template v-if="draft.special.length">
            <span class="plus">+</span>
            <button
              v-for="(n, i) in draft.special"
              :key="'ds' + n + i"
              type="button"
              class="ball xs"
              :class="specialBallClass"
              title="移出"
              @click="dropAt('special', i)"
            >{{ n }}</button>
          </template>
          <span v-if="!hasDraft" class="text-sm text-muted">点表头或开出的球</span>
        </template>
      </div>
      <span class="trend-draft-hint">{{ draftState.message }}</span>
      <div class="trend-draft-actions">
        <button type="button" class="text-btn" :disabled="!hasDraft" @click="clearDraft">清空</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="!draftState.complete" @click="addDraft">加入选号篮</button>
      </div>
    </div>

    <div v-if="!rows.length" class="text-sm text-muted">暂无开奖数据</div>
    <div v-else ref="scrollEl" class="trend-scroll" @scroll="onScroll">
      <div class="trend-canvas-wrap" :style="{ minWidth: tableMinWidth + 'px' }">
        <svg
          v-if="specialPool.length && blueLine.length > 1"
          class="trend-blue-line"
          :width="tableMinWidth"
          :height="svgHeight"
          :viewBox="`0 0 ${tableMinWidth} ${svgHeight}`"
        >
          <polyline
            fill="none"
            stroke="var(--trend-line, rgba(74, 120, 184, 0.5))"
            stroke-width="1.6"
            :points="blueLine.map((p) => `${p.x},${p.y}`).join(' ')"
          />
        </svg>
        <table class="trend-table" ref="tableEl">
          <thead>
            <template v-if="zoneLabels.length">
              <tr class="zone-row">
                <th class="sticky-col" :rowspan="2">期号</th>
                <th class="sticky-col-2" :rowspan="2">日期</th>
                <th
                  v-for="z in zoneLabels"
                  :key="z.label"
                  class="zone-head"
                  :class="'zone-' + z.idx"
                  :colspan="z.span"
                >{{ z.label }}</th>
                <th v-if="specialPool.length" class="sep-col" :rowspan="2"></th>
                <th
                  v-if="specialPool.length"
                  class="special-zone"
                  :colspan="specialPool.length"
                >特别号</th>
                <th class="stat-head" :rowspan="2">和值</th>
                <th class="stat-head" :rowspan="2">跨度</th>
                <th class="stat-head" :rowspan="2">奇偶</th>
                <th class="stat-head" :rowspan="2">区间</th>
              </tr>
              <tr>
                <th
                  v-for="n in mainPool"
                  :key="'mh' + n"
                  class="num-col"
                  :class="[zoneClass(n), picked('main', n)]"
                >
                  <button type="button" class="trend-num-btn" :aria-pressed="isOn('main', n)" @click="onPick('main', n)">{{ n }}</button>
                </th>
                <th
                  v-for="n in specialPool"
                  :key="'sh' + n"
                  class="num-col special-head"
                  :class="picked('special', n)"
                >
                  <button type="button" class="trend-num-btn" :aria-pressed="isOn('special', n)" @click="onPick('special', n)">{{ n }}</button>
                </th>
              </tr>
            </template>
            <tr v-else>
              <th class="sticky-col">期号</th>
              <th class="sticky-col-2">日期</th>
              <th v-for="n in mainPool" :key="'mh2' + n" class="num-col" :class="picked('main', n)">
                <button type="button" class="trend-num-btn" :aria-pressed="isOn('main', n)" @click="onPick('main', n)">{{ n }}</button>
              </th>
              <th v-if="specialPool.length" class="sep-col"></th>
              <th
                v-for="n in specialPool"
                :key="'sh2' + n"
                class="num-col special-head"
                :class="picked('special', n)"
              >
                <button type="button" class="trend-num-btn" :aria-pressed="isOn('special', n)" @click="onPick('special', n)">{{ n }}</button>
              </th>
              <th class="stat-head">和值</th>
              <th class="stat-head">跨度</th>
              <th class="stat-head">奇偶</th>
              <th class="stat-head">区间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in rows" :key="row.issue" :data-ri="ri">
              <td class="sticky-col mono">{{ row.issue }}</td>
              <td class="sticky-col-2 muted">{{ shortDate(row.draw_date) }}</td>
              <td
                v-for="n in mainPool"
                :key="row.issue + 'm' + n"
                class="num-col"
                :class="[zoneClass(n), picked('main', n)]"
              >
                <button
                  v-if="row.mainSet.has(n)"
                  type="button"
                  class="ball xs"
                  :class="mainBallClass"
                  @click="onPick('main', n)"
                >{{ n }}</button>
                <span v-else :class="heatClass(row.mainOmit[n], mainOmitMax)">{{ row.mainOmit[n] }}</span>
              </td>
              <td v-if="specialPool.length" class="sep-col"></td>
              <td
                v-for="n in specialPool"
                :key="row.issue + 's' + n"
                class="num-col blue-cell"
                :class="picked('special', n)"
                :data-n="n"
                :data-hit="row.specialSet.has(n) ? '1' : '0'"
              >
                <button
                  v-if="row.specialSet.has(n)"
                  type="button"
                  class="ball xs blue-hit"
                  :class="specialBallClass"
                  :data-blue-anchor="row.issue"
                  @click="onPick('special', n)"
                >{{ n }}</button>
                <span v-else :class="heatClass(row.specialOmit[n], specialOmitMax)">{{ row.specialOmit[n] }}</span>
              </td>
              <td class="stat-cell">{{ row.sum }}</td>
              <td class="stat-cell">{{ row.span }}</td>
              <td class="stat-cell">
                <span class="tag odd">{{ row.odd }}</span>:<span class="tag even">{{ row.even }}</span>
              </td>
              <td class="stat-cell mono">{{ row.zoneRatio }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td class="sticky-col" colspan="2">出现次数</td>
              <td v-for="n in mainPool" :key="'mc' + n" class="num-col foot" :class="picked('main', n)">{{ mainCounts[n] || 0 }}</td>
              <td v-if="specialPool.length" class="sep-col"></td>
              <td v-for="n in specialPool" :key="'sc' + n" class="num-col foot" :class="picked('special', n)">{{ specialCounts[n] || 0 }}</td>
              <td class="stat-cell foot" colspan="4"></td>
            </tr>
            <tr>
              <td class="sticky-col" colspan="2">平均遗漏</td>
              <td v-for="n in mainPool" :key="'ma' + n" class="num-col foot" :class="picked('main', n)">{{ mainAvgOmit[n] }}</td>
              <td v-if="specialPool.length" class="sep-col"></td>
              <td v-for="n in specialPool" :key="'sa' + n" class="num-col foot" :class="picked('special', n)">{{ specialAvgOmit[n] }}</td>
              <td class="stat-cell foot" colspan="4"></td>
            </tr>
            <tr>
              <td class="sticky-col" colspan="2">最大遗漏</td>
              <td v-for="n in mainPool" :key="'mm' + n" class="num-col foot" :class="picked('main', n)">{{ mainMaxOmit[n] || 0 }}</td>
              <td v-if="specialPool.length" class="sep-col"></td>
              <td v-for="n in specialPool" :key="'sm' + n" class="num-col foot" :class="picked('special', n)">{{ specialMaxOmit[n] || 0 }}</td>
              <td class="stat-cell foot" colspan="4"></td>
            </tr>
            <tr>
              <td class="sticky-col" colspan="2">最大连出</td>
              <td v-for="n in mainPool" :key="'ml' + n" class="num-col foot" :class="picked('main', n)">{{ mainMaxStreak[n] || 0 }}</td>
              <td v-if="specialPool.length" class="sep-col"></td>
              <td v-for="n in specialPool" :key="'sl' + n" class="num-col foot" :class="picked('special', n)">{{ specialMaxStreak[n] || 0 }}</td>
              <td class="stat-cell foot" colspan="4"></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ballClass } from '../api'
import { toast } from '../composables/feedback'
import { useBasket } from '../composables/useBasket'
import {
  emptyTrendDraft,
  isTrendPicked,
  omitHeatLevel,
  omitHeatMax,
  removeTrendAt,
  toggleTrendNumber,
  trendDraftState,
  trendRule,
} from '../lib/trendPick'

const props = defineProps({
  type: { type: String, default: 'ssq' },
  draws: { type: Array, default: () => [] },
  periods: { type: Number, default: 50 },
  periodOptions: { type: Array, default: () => [50, 80, 120, 300] },
})

defineEmits(['update:periods'])

const basket = useBasket()
const draft = ref(emptyTrendDraft())
const tableEl = ref(null)
const scrollEl = ref(null)
const blueLine = ref([])
const svgHeight = ref(0)
const tableMinWidth = ref(900)

const COL_W = 22
const STICKY_W = 64 + 48

function range(lo, hi, width) {
  const out = []
  for (let i = lo; i <= hi; i++) out.push(width > 1 ? String(i).padStart(width, '0') : String(i))
  return out
}

const POOLS = {
  ssq: {
    main: range(1, 33, 2),
    special: range(1, 16, 2),
    zones: [[1, 11, '一区'], [12, 22, '二区'], [23, 33, '三区']],
  },
  dlt: {
    main: range(1, 35, 2),
    special: range(1, 12, 2),
    zones: [[1, 12, '一区'], [13, 24, '二区'], [25, 35, '三区']],
  },
  fc3d: { main: range(0, 9, 1), special: [], zones: [] },
  pl3: { main: range(0, 9, 1), special: [], zones: [] },
  pl5: { main: range(0, 9, 1), special: [], zones: [] },
  qxc: { main: range(0, 9, 1), special: range(0, 14, 1), zones: [] },
  qlc: {
    main: range(1, 30, 2),
    special: range(1, 30, 2),
    zones: [[1, 10, '一区'], [11, 20, '二区'], [21, 30, '三区']],
  },
  kl8: {
    main: range(1, 80, 2),
    special: [],
    zones: [[1, 20, '一区'], [21, 40, '二区'], [41, 60, '三区'], [61, 80, '四区']],
  },
}

const pool = computed(() => POOLS[props.type] || POOLS.ssq)
const mainPool = computed(() => pool.value.main)
const specialPool = computed(() => pool.value.special)
const mainBallClass = computed(() => ballClass(props.type, 'main'))
const specialBallClass = computed(() => ballClass(props.type, 'special'))

const zoneLabels = computed(() =>
  (pool.value.zones || []).map((z, idx) => ({
    label: z[2] || `区${idx + 1}`,
    span: mainPool.value.filter((n) => {
      const v = parseInt(n, 10)
      return v >= z[0] && v <= z[1]
    }).length,
    idx,
  })).filter((z) => z.span > 0),
)

function zoneClass(n) {
  const zones = pool.value.zones || []
  const v = parseInt(n, 10)
  const idx = zones.findIndex((z) => v >= z[0] && v <= z[1])
  return idx >= 0 ? `zone-${idx}` : ''
}

function shortDate(d) {
  if (!d) return '—'
  const s = String(d)
  return s.length >= 10 ? s.slice(5, 10) : s
}

function asSet(list) {
  return new Set((list || []).map((x) => String(x)))
}

function zoneRatio(mains, zones) {
  if (!zones.length) return '—'
  const counts = zones.map(([a, b]) =>
    mains.filter((n) => {
      const v = parseInt(n, 10)
      return v >= a && v <= b
    }).length,
  )
  return counts.join(':')
}

const rows = computed(() => {
  const list = (props.draws || []).slice(0, props.periods)
  const mainOmit = Object.fromEntries(mainPool.value.map((n) => [n, 0]))
  const specialOmit = Object.fromEntries(specialPool.value.map((n) => [n, 0]))
  const chronological = [...list].reverse()
  const built = []
  for (const d of chronological) {
    const nums = d.numbers || { main: [], special: [] }
    const mains = (nums.main || []).map(String)
    const specs = (nums.special || []).map(String)
    const mainSet = asSet(mains)
    const specialSet = asSet(specs)
    const rowMainOmit = {}
    const rowSpecialOmit = {}
    for (const n of mainPool.value) {
      if (mainSet.has(n)) {
        rowMainOmit[n] = 0
        mainOmit[n] = 0
      } else {
        mainOmit[n] = (mainOmit[n] || 0) + 1
        rowMainOmit[n] = mainOmit[n]
      }
    }
    for (const n of specialPool.value) {
      if (specialSet.has(n)) {
        rowSpecialOmit[n] = 0
        specialOmit[n] = 0
      } else {
        specialOmit[n] = (specialOmit[n] || 0) + 1
        rowSpecialOmit[n] = specialOmit[n]
      }
    }
    const ints = mains.map((x) => parseInt(x, 10)).filter((x) => !Number.isNaN(x))
    const sum = ints.reduce((a, b) => a + b, 0)
    const span = ints.length ? Math.max(...ints) - Math.min(...ints) : 0
    const odd = ints.filter((x) => x % 2 === 1).length
    const even = ints.length - odd
    built.push({
      issue: d.issue,
      draw_date: d.draw_date,
      mainSet,
      specialSet,
      specialHit: specs[0] || '',
      mainOmit: { ...rowMainOmit },
      specialOmit: { ...rowSpecialOmit },
      sum,
      span,
      odd,
      even,
      zoneRatio: zoneRatio(mains, pool.value.zones || []),
    })
  }
  return built.reverse()
})

const mainCounts = computed(() => {
  const c = Object.fromEntries(mainPool.value.map((n) => [n, 0]))
  for (const row of rows.value) for (const n of row.mainSet) if (n in c) c[n]++
  return c
})
const specialCounts = computed(() => {
  const c = Object.fromEntries(specialPool.value.map((n) => [n, 0]))
  for (const row of rows.value) for (const n of row.specialSet) if (n in c) c[n]++
  return c
})

function maxOmit(poolList, key) {
  const best = Object.fromEntries(poolList.map((n) => [n, 0]))
  const run = Object.fromEntries(poolList.map((n) => [n, 0]))
  for (const row of [...rows.value].reverse()) {
    const set = key === 'main' ? row.mainSet : row.specialSet
    for (const n of poolList) {
      if (set.has(n)) run[n] = 0
      else {
        run[n]++
        if (run[n] > best[n]) best[n] = run[n]
      }
    }
  }
  return best
}

function maxStreak(poolList, key) {
  const best = Object.fromEntries(poolList.map((n) => [n, 0]))
  const run = Object.fromEntries(poolList.map((n) => [n, 0]))
  for (const row of [...rows.value].reverse()) {
    const set = key === 'main' ? row.mainSet : row.specialSet
    for (const n of poolList) {
      if (set.has(n)) {
        run[n]++
        if (run[n] > best[n]) best[n] = run[n]
      } else run[n] = 0
    }
  }
  return best
}

function avgOmit(poolList, counts) {
  const nRows = rows.value.length || 1
  const out = {}
  for (const n of poolList) {
    const hit = counts[n] || 0
    out[n] = hit ? Math.round((nRows - hit) / hit) : nRows
  }
  return out
}

const mainMaxOmit = computed(() => maxOmit(mainPool.value, 'main'))
const specialMaxOmit = computed(() => maxOmit(specialPool.value, 'special'))
const mainMaxStreak = computed(() => maxStreak(mainPool.value, 'main'))
const specialMaxStreak = computed(() => maxStreak(specialPool.value, 'special'))
const mainAvgOmit = computed(() => avgOmit(mainPool.value, mainCounts.value))
const specialAvgOmit = computed(() => avgOmit(specialPool.value, specialCounts.value))
const mainOmitMax = computed(() => omitHeatMax(rows.value, 'mainOmit'))
const specialOmitMax = computed(() => omitHeatMax(rows.value, 'specialOmit'))
const rule = computed(() => trendRule(props.type))
const draftState = computed(() => trendDraftState(props.type, draft.value))
const hasDraft = computed(() => draft.value.main.length + draft.value.special.length > 0)

function isOn(zone, n) {
  return isTrendPicked(props.type, draft.value, zone, n)
}

function picked(zone, n) {
  return isOn(zone, n) ? 'pick-on' : ''
}

function heatClass(value, max) {
  const level = omitHeatLevel(value, max)
  return level ? ['omit', `heat-${level}`] : ['omit']
}

function onPick(zone, n) {
  const result = toggleTrendNumber(props.type, draft.value, zone, n)
  draft.value = result.draft
  if ((result.status === 'full' || result.status === 'invalid') && result.message) {
    toast(result.message, result.status === 'full' ? 'info' : 'error')
  }
}

function dropAt(zone, index) {
  draft.value = removeTrendAt(draft.value, zone, index)
}

function clearDraft() {
  draft.value = emptyTrendDraft()
}

function addDraft() {
  const state = trendDraftState(props.type, draft.value)
  if (!state.complete) {
    toast(state.message, 'info')
    return
  }
  const outcome = basket.add({
    lottery_type: props.type,
    numbers: state.numbers,
    source: 'manual',
    note: '走势点选',
  })
  const kind = outcome.status === 'added' ? 'ok' : outcome.status === 'duplicate' ? 'info' : 'error'
  toast(outcome.message, kind)
  if (outcome.status === 'added') draft.value = emptyTrendDraft()
}

function specialIndex(hit) {
  if (hit == null || hit === '') return -1
  const s = String(hit)
  const pool = specialPool.value
  let idx = pool.indexOf(s)
  if (idx >= 0) return idx
  const n = parseInt(s, 10)
  if (Number.isNaN(n)) return -1
  return pool.findIndex((x) => parseInt(x, 10) === n)
}

function measureBlueLine() {
  const table = tableEl.value
  if (!table || !specialPool.value.length) {
    blueLine.value = []
    return
  }
  const thead = table.tHead
  const firstBody = table.tBodies[0]?.rows?.[0]
  const headerH = thead ? thead.offsetHeight : 52
  const rowH = firstBody ? firstBody.offsetHeight : 26
  const sticky1 = table.querySelector('tbody .sticky-col') || table.querySelector('.sticky-col')
  const sticky2 = table.querySelector('tbody .sticky-col-2') || table.querySelector('.sticky-col-2')
  const sep = table.querySelector('tbody .sep-col') || table.querySelector('.sep-col')
  const sampleMain = table.querySelector('tbody td.num-col:not(.blue-cell)')
  const sampleBlue = table.querySelector('tbody td.blue-cell')
  const stickyW = (sticky1?.offsetWidth || 64) + (sticky2?.offsetWidth || 48)
  const mainCellW = sampleMain?.offsetWidth || COL_W
  const blueCellW = sampleBlue?.offsetWidth || COL_W
  const sepW = specialPool.value.length ? (sep?.offsetWidth || 8) : 0
  const specialOriginX = stickyW + mainPool.value.length * mainCellW + sepW

  const points = []
  rows.value.forEach((row, i) => {
    const idx = specialIndex(row.specialHit)
    if (idx < 0) return
    points.push({
      x: specialOriginX + idx * blueCellW + blueCellW / 2,
      y: headerH + i * rowH + rowH / 2,
    })
  })
  blueLine.value = points
  svgHeight.value = Math.max(table.scrollHeight, 100)
  const scroll = scrollEl.value
  tableMinWidth.value = Math.max(table.scrollWidth, scroll?.clientWidth || 0, 900)
}

function onScroll() {
  /* 折线用格子几何，不随滚动重算 */
}

watch([rows, () => props.type, () => props.periods], async () => {
  await nextTick()
  requestAnimationFrame(measureBlueLine)
})

watch(() => props.type, () => {
  draft.value = emptyTrendDraft()
})

onMounted(async () => {
  await nextTick()
  requestAnimationFrame(measureBlueLine)
  window.addEventListener('resize', measureBlueLine)
})
</script>
