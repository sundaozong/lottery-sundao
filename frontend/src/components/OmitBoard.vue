<template>
  <div id="omit-board" class="card mb-4">
    <div class="card-title">
      遗漏看板
      <span class="sub">当前 / 平均 / 最大 · 不参与脉动</span>
    </div>
    <div class="alert alert-disclaimer">
      <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
      <div>{{ board?.disclaimer || '遗漏看板仅供娱乐，不构成投注建议。' }}</div>
    </div>

    <div class="omit-toolbar">
      <div class="chip-row compact">
        <button
          v-for="item in limits"
          :key="item"
          type="button"
          class="chip"
          :class="{ active: limit === item }"
          @click="setLimit(item)"
        >{{ item }} 期</button>
      </div>
      <div class="chip-row compact">
        <button
          v-for="item in sorts"
          :key="item.key"
          type="button"
          class="chip"
          :class="{ active: sort === item.key }"
          @click="setSort(item.key)"
        >{{ item.label }}</button>
      </div>
    </div>

    <div class="chip-row compact">
      <button type="button" class="chip" :class="{ active: mode === 'dan' }" @click="mode = 'dan'">选胆</button>
      <button type="button" class="chip" :class="{ active: mode === 'kill' }" @click="mode = 'kill'">选杀</button>
      <button type="button" class="chip" :class="{ active: mode === 'pick' }" @click="mode = 'pick'">点选组注</button>
      <template v-if="hasSpecial">
        <button type="button" class="chip" :class="{ active: zone === 'main' }" @click="zone = 'main'">主号</button>
        <button type="button" class="chip" :class="{ active: zone === 'special' }" @click="zone = 'special'">{{ specialLabel }}</button>
      </template>
    </div>
    <p class="form-hint">{{ modeHint }}</p>
    <div class="omit-legend">
      <span><i class="hot" />热 · 刚开出</span>
      <span><i class="warm" />温 · 低于平均</span>
      <span><i class="cool" />凉 · 接近或超过平均</span>
      <span><i class="cold" />冷 · {{ board?.cold_rule || '偏冷' }}</span>
    </div>

    <p v-if="error" class="bet-error">{{ error }}</p>
    <div v-if="loading && !board" class="loading-line">
      <AppIcon name="sync" :size="15" class="spin" />统计遗漏…
    </div>
    <template v-else-if="board">
      <p class="text-xs text-muted">样本 {{ board.sample_size }} 期 · 请求窗 {{ board.limit }} 期</p>
      <div class="omit-grid" :class="{ scroll: poolLarge && !expanded }">
        <button
          v-for="row in zoneRows"
          :key="row.n"
          type="button"
          class="omit-cell"
          :class="[heatTone(row), markClass(row.n)]"
          :aria-label="`${row.n} 当前遗漏 ${row.current}`"
          :title="cellTitle(row)"
          @click="onNumber(row.n)"
        >
          <span class="omit-n">{{ row.n }}</span>
          <span class="omit-cur">{{ row.current }}</span>
        </button>
      </div>
      <button
        v-if="poolLarge"
        class="btn btn-ghost btn-sm"
        type="button"
        @click="expanded = !expanded"
      >{{ expanded ? '收起号码格' : '展开全部号码' }}</button>

      <div v-if="selectionText" class="omit-selected">{{ selectionText }}</div>
      <div class="predict-actions">
        <button class="btn btn-primary btn-sm" type="button" @click="applyConstraints">应用到机选条件</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="addCold">冷号组一注入篮</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="copySummary">复制遗漏摘要</button>
        <button class="btn btn-ghost btn-sm" type="button" :disabled="!pickReady" @click="addPick">点选组注入篮</button>
      </div>
      <pre class="omit-summary">{{ summaryText }}</pre>

      <div class="table-wrap omit-table">
        <table>
          <thead>
            <tr>
              <th>号码</th>
              <th>当前</th>
              <th>平均</th>
              <th>最大</th>
              <th>次数</th>
              <th>出现率</th>
              <th>比值</th>
              <th>最近开出</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in zoneRows" :key="`row-${row.n}`" :class="{ 'omit-cold-row': row.cold }">
              <td>
                <button type="button" class="omit-table-n" @click="onNumber(row.n)">{{ row.n }}</button>
              </td>
              <td class="mono">{{ row.current }}</td>
              <td class="mono">{{ formatNum(row.avg) }}</td>
              <td class="mono">{{ row.max }}</td>
              <td class="mono">{{ row.count }}</td>
              <td class="mono">{{ formatRate(row.rate) }}</td>
              <td class="mono">{{ formatNum(row.ratio) }}</td>
              <td class="mono">{{ row.last_issue || '—' }}</td>
              <td>{{ row.cold ? '偏冷' : (row.current === 0 ? '刚开' : '—') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, TYPE_NAMES } from '../api'
import AppIcon from './AppIcon.vue'
import { toast } from '../composables/feedback'
import { useBasket } from '../composables/useBasket'
import { basketProfile } from '../lib/basket.js'
import {
  coldTicket,
  constraintStorageKey,
  emptyMarks,
  hasConstraintMarks,
  heatTone,
  markOf,
  omitSummary,
  ticketPlan,
  toggleMark,
  writePredictConstraints,
} from '../lib/omitBoard.js'
import { trendDraftState } from '../lib/trendPick.js'

const props = defineProps({
  type: { type: String, required: true },
})

const basket = useBasket()
const route = useRoute()
const limits = [20, 50, 80, 120, 200]
const sorts = [
  { key: 'n', label: '号码' },
  { key: 'current', label: '当前' },
  { key: 'ratio', label: '比值' },
  { key: 'max', label: '最大' },
  { key: 'count', label: '次数' },
]
const limit = ref(80)
const sort = ref('n')
const mode = ref('dan')
const zone = ref('main')
const board = ref(null)
const marks = ref(emptyMarks())
const loading = ref(false)
const error = ref('')
const expanded = ref(false)
let token = 0

const specialLabel = computed(() => basketProfile(props.type)?.specialLabel || '特别号')
const hasSpecial = computed(() => (board.value?.special || []).length > 0)
const zoneRows = computed(() => (zone.value === 'special' ? board.value?.special : board.value?.main) || [])
const poolLarge = computed(() => (board.value?.main || []).length > 40)
const modeHint = computed(() => ({
  dan: '点号码设为胆码，再点一次取消。同一号码不会同时是胆和杀。',
  kill: '点号码设为杀号，再点一次取消。',
  pick: '按这个彩种的注数点选一注。数字彩按点击顺序排位。',
}[mode.value]))
const pickState = computed(() => trendDraftState(props.type, marks.value.pick))
const pickReady = computed(() => pickState.value.complete)
const summaryText = computed(() => omitSummary(board.value || { sample_size: 0, main: [], special: [] }, TYPE_NAMES[props.type] || props.type))
const selectionText = computed(() => {
  const parts = []
  if (marks.value.danMain.length) parts.push(`胆 ${marks.value.danMain.join(' ')}`)
  if (marks.value.killMain.length) parts.push(`杀 ${marks.value.killMain.join(' ')}`)
  if (marks.value.danSpecial.length) parts.push(`${specialLabel.value}胆 ${marks.value.danSpecial.join(' ')}`)
  if (marks.value.killSpecial.length) parts.push(`${specialLabel.value}杀 ${marks.value.killSpecial.join(' ')}`)
  if (marks.value.pick.main.length || marks.value.pick.special.length) {
    const main = marks.value.pick.main.join(' ')
    const special = marks.value.pick.special.join(' ')
    parts.push(`组注 ${main}${special ? ` + ${special}` : ''}`)
  }
  if (mode.value === 'pick' && pickState.value.message) parts.push(pickState.value.message)
  return parts.join(' · ')
})

function markClass(number) {
  const kind = markOf(marks.value, zone.value, number)
  return kind ? `mark-${kind}` : ''
}

function cellTitle(row) {
  const state = row.cold ? '偏冷' : '未标偏冷'
  return `${row.n} 当前 ${row.current} 平均 ${formatNum(row.avg)} 最大 ${row.max} 比值 ${formatNum(row.ratio)} ${state}`
}

function formatNum(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return number.toFixed(2)
}

function formatRate(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${(number * 100).toFixed(1)}%`
}

async function load() {
  const current = ++token
  loading.value = true
  error.value = ''
  try {
    const data = await api.omitBoard(props.type, { limit: limit.value, sort: sort.value })
    if (current !== token) return
    board.value = data
    if (zone.value === 'special' && !(data.special || []).length) zone.value = 'main'
  } catch (err) {
    if (current !== token) return
    error.value = err?.message || '遗漏看板加载失败'
  } finally {
    if (current === token) loading.value = false
  }
}

function setLimit(value) {
  if (limit.value === value) return
  limit.value = value
  load()
}

function setSort(value) {
  if (sort.value === value) return
  sort.value = value
  load()
}

function onNumber(number) {
  const step = toggleMark(props.type, marks.value, zone.value, number, mode.value)
  if (step.status === 'invalid' || step.status === 'full') {
    toast(step.message || '这个号加不进去', 'error')
  }
  if (step.status !== 'invalid') marks.value = step.marks
}

function readConstraints() {
  try {
    const raw = localStorage.getItem(constraintStorageKey(props.type))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function applyConstraints() {
  if (!hasConstraintMarks(marks.value)) {
    toast('先点选胆码或杀号', 'error')
    return
  }
  const plan = ticketPlan(props.type)
  if (plan && marks.value.danMain.length > plan.danMain) {
    toast('胆码超过机选上限', 'error')
    return
  }
  writePredictConstraints(localStorage, props.type, marks.value, readConstraints())
  toast('已写入机选条件，到预测页即可使用', 'ok')
}

function addCold() {
  const ticket = coldTicket(props.type, board.value)
  if (!ticket.ok) {
    toast(ticket.message, 'error')
    return
  }
  const result = basket.add({
    lottery_type: props.type,
    numbers: ticket.numbers,
    source: 'omit',
    note: '遗漏偏冷',
  })
  toast(result.message, result.status === 'added' ? 'ok' : 'error')
}

function addPick() {
  if (!pickReady.value) {
    toast(pickState.value.message || '这注还没点满', 'error')
    return
  }
  const result = basket.add({
    lottery_type: props.type,
    numbers: pickState.value.numbers,
    source: 'omit',
    note: '遗漏点选',
  })
  toast(result.message, result.status === 'added' ? 'ok' : 'error')
}

async function copySummary() {
  const text = summaryText.value
  try {
    await navigator.clipboard.writeText(text)
    toast('已复制遗漏摘要', 'ok')
  } catch {
    toast('复制失败，可从下方摘要里手动复制', 'error')
  }
}

watch(() => props.type, () => {
  marks.value = emptyMarks()
  zone.value = 'main'
  expanded.value = false
  load()
})

onMounted(() => {
  load()
  if (route.hash === '#omit-board') {
    requestAnimationFrame(() => {
      document.getElementById('omit-board')?.scrollIntoView({ block: 'start' })
    })
  }
})
</script>
