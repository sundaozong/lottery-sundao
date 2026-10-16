<template>
  <div>
    <div class="page-header">
      <div>
        <h1>购买记录</h1>
        <p>流水 · 盈亏汇总 · CRUD</p>
      </div>
      <button class="btn btn-primary btn-sm" type="button" @click="openForm">
        {{ showForm ? '收起' : '+ 记一笔' }}
      </button>
    </div>

    <div class="grid grid-3 mb-4">
      <div class="card stat">
        <div class="stat-label">投入</div>
        <div class="stat-value">¥ {{ summary.total_cost ?? 0 }}</div>
      </div>
      <div class="card stat">
        <div class="stat-label">奖金</div>
        <div class="stat-value ok">¥ {{ summary.total_prize ?? 0 }}</div>
      </div>
      <div class="card stat">
        <div class="stat-label">净盈亏</div>
        <div class="stat-value" :class="(summary.net || 0) >= 0 ? 'ok' : 'danger'">
          ¥ {{ summary.net ?? 0 }}
        </div>
      </div>
    </div>

    <div v-if="showForm" class="card mb-4">
      <div class="card-title">{{ editingId ? '编辑记录' : '新增记录' }}</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">彩种</label>
          <select v-model="form.lottery_type" class="form-select">
            <option v-for="(name, key) in TYPE_NAMES" :key="key" :value="key">{{ name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">期号</label>
          <input v-model="form.issue" class="form-input mono" placeholder="自动填入最新期" />
          <p v-if="latestDraw" class="form-hint">
            最新期 {{ latestDraw.issue }}<template v-if="latestDraw.draw_date"> · {{ latestDraw.draw_date }}</template>
            <button v-if="form.issue !== latestDraw.issue" class="text-btn" type="button" @click="form.issue = latestDraw.issue">填入最新期</button>
          </p>
        </div>
      </div>
      <BetFields
        :lottery-type="form.lottery_type"
        :play-state="bet"
        :draw="matchedDraw"
        @update:play-state="bet = $event"
        @result="onCalc"
      />
      <div class="form-row mt-3">
        <div class="form-group">
          <label class="form-label">投入(元)</label>
          <input :value="form.cost" type="number" step="0.01" class="form-input" @input="onCostInput" />
          <p class="form-hint">按注数自动计算，可以改</p>
        </div>
        <div class="form-group">
          <label class="form-label">奖金(元)</label>
          <input :value="form.prize" type="number" step="0.01" class="form-input" @input="onPrizeInput" />
          <p class="form-hint">按本期开奖和右侧奖金表估算，可以改</p>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">购买日期</label>
          <input v-model="form.purchased_at" class="form-input" placeholder="2026-10-15" />
        </div>
        <div class="form-group">
          <label class="form-label">备注</label>
          <input v-model="form.note" class="form-input" />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="button" @click="save">保存</button>
        <button class="btn btn-ghost" type="button" @click="resetForm">取消</button>
      </div>
    </div>

    <div class="card">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>彩种</th><th>期号</th><th>号码</th><th>投入</th><th>奖金</th><th>盈亏</th><th>日期</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in items" :key="r.id">
              <td>{{ r.name }}</td>
              <td class="mono">{{ r.issue }}</td>
              <td>
                <div v-if="r.play_name" class="text-xs text-muted">{{ r.play_name }}</div>
                <NumberBalls :numbers="r.numbers" :type="r.lottery_type" size="sm" />
              </td>
              <td class="mono">{{ r.cost }}</td>
              <td class="mono">{{ r.prize }}</td>
              <td class="mono" :class="r.profit >= 0 ? 'profit-pos' : 'profit-neg'">{{ r.profit }}</td>
              <td class="text-xs">{{ r.purchased_at }}</td>
              <td>
                <button class="btn btn-ghost btn-sm" type="button" @click="edit(r)">改</button>
                <button class="btn btn-danger btn-sm" type="button" @click="remove(r.id)">删</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!items.length" class="empty"><div class="icon">☰</div>暂无记录</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch, onMounted } from 'vue'
import { api, TYPE_NAMES } from '../api'
import NumberBalls from '../components/NumberBalls.vue'
import BetFields from '../components/BetFields.vue'

const items = ref([])
const summary = ref({})
const showForm = ref(false)
const editingId = ref(null)
const form = ref(blank())
const bet = ref(defaultBet('ssq'))
const drawsByType = ref({})
const costTouched = ref(false)
const prizeTouched = ref(false)
let muteType = false

function blank() {
  return {
    lottery_type: 'ssq',
    issue: '',
    cost: 2,
    prize: 0,
    note: '',
    purchased_at: new Date().toISOString().slice(0, 10),
  }
}

function defaultBet(type) {
  const count = type === 'pl5' ? 5 : type === 'qxc' ? 7 : 3
  const play = type === 'kl8' ? 'pick' : (type === 'fc3d' || type === 'pl3' || type === 'pl5' ? 'direct' : 'single')
  return {
    play,
    pick: 10,
    mainText: '',
    specialText: '',
    positions: Array.from({ length: count }, () => ''),
    multiple: 1,
  }
}

function split(text) {
  return String(text || '').trim().split(/[\s,]+/).filter(Boolean)
}

function betFromRecord(r) {
  const numbers = r.numbers || {}
  const base = defaultBet(r.lottery_type)
  let positions = base.positions
  if (numbers.positions?.length) {
    positions = base.positions.map((_, i) => (numbers.positions[i] || []).join(' '))
  } else if (['fc3d', 'pl3', 'pl5', 'qxc'].includes(r.lottery_type)) {
    const all = r.lottery_type === 'qxc'
      ? [...(numbers.main || []), ...(numbers.special || [])]
      : (numbers.main || [])
    positions = base.positions.map((_, i) => (all[i] != null ? String(all[i]) : ''))
  }
  return {
    play: numbers.play || base.play,
    pick: numbers.pick || base.pick,
    mainText: (numbers.main || []).join(' '),
    specialText: (numbers.special || []).join(' '),
    positions,
    multiple: numbers.multiple || 1,
  }
}

function betPayload() {
  return {
    play: bet.value.play,
    pick: bet.value.pick,
    multiple: bet.value.multiple,
    main: split(bet.value.mainText),
    special: split(bet.value.specialText),
    positions: bet.value.positions.map(split),
  }
}

function pickLatest(rows) {
  return [...rows].sort((a, b) => (Number(b.issue) || 0) - (Number(a.issue) || 0))[0] || null
}

const latestDraw = computed(() => pickLatest(drawsByType.value[form.value.lottery_type] || []))
const matchedDraw = computed(() => {
  const rows = drawsByType.value[form.value.lottery_type] || []
  return rows.find((row) => row.issue === String(form.value.issue || '').trim()) || null
})

async function loadDraws(type) {
  const res = await api.draws(type, 200)
  drawsByType.value = { ...drawsByType.value, [type]: res.items || [] }
}

async function onTypeChange() {
  await loadDraws(form.value.lottery_type)
  if (muteType) return
  const latest = pickLatest(drawsByType.value[form.value.lottery_type] || [])
  form.value.issue = latest?.issue || ''
  bet.value = defaultBet(form.value.lottery_type)
  costTouched.value = false
  prizeTouched.value = false
}

watch(() => form.value.lottery_type, (next, prev) => {
  if (!prev || next === prev || muteType) return
  onTypeChange()
})

watch(bet, () => {
  if (muteType) return
  costTouched.value = false
  prizeTouched.value = false
}, { deep: true })

watch(() => form.value.issue, () => {
  if (muteType) return
  prizeTouched.value = false
})

function onCalc(res) {
  if (!res) return
  if (!costTouched.value) form.value.cost = res.cost
  if (!prizeTouched.value) form.value.prize = res.opened ? res.amount : 0
}

function onCostInput(event) {
  form.value.cost = Number(event.target.value)
  costTouched.value = true
}

function onPrizeInput(event) {
  form.value.prize = Number(event.target.value)
  prizeTouched.value = true
}

async function load() {
  const res = await api.records()
  items.value = res.items || []
  summary.value = res.summary || {}
}

function resetForm() {
  form.value = blank()
  bet.value = defaultBet('ssq')
  editingId.value = null
  showForm.value = false
  costTouched.value = false
  prizeTouched.value = false
}

async function openForm() {
  if (showForm.value) {
    resetForm()
    return
  }
  editingId.value = null
  form.value = blank()
  bet.value = defaultBet('ssq')
  showForm.value = true
  await onTypeChange()
}

async function edit(r) {
  muteType = true
  editingId.value = r.id
  showForm.value = true
  costTouched.value = true
  prizeTouched.value = true
  form.value = {
    lottery_type: r.lottery_type,
    issue: r.issue,
    cost: r.cost,
    prize: r.prize,
    note: r.note,
    purchased_at: r.purchased_at,
  }
  bet.value = betFromRecord(r)
  await nextTick()
  await loadDraws(r.lottery_type)
  muteType = false
}

async function save() {
  const body = {
    lottery_type: form.value.lottery_type,
    issue: form.value.issue,
    numbers: betPayload(),
    cost: form.value.cost,
    prize: form.value.prize,
    note: form.value.note,
    purchased_at: form.value.purchased_at,
  }
  try {
    if (editingId.value) await api.updateRecord(editingId.value, body)
    else await api.createRecord(body)
    resetForm()
    await load()
  } catch (e) {
    alert(e.message)
  }
}

async function remove(id) {
  if (!confirm('确认删除？')) return
  await api.deleteRecord(id)
  await load()
}

onMounted(load)
</script>
