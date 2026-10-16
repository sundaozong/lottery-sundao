<template>
  <div>
    <div class="page-header">
      <div>
        <h1>奖金计算</h1>
        <p>选号 vs 开奖 · 简化固定奖规则</p>
      </div>
    </div>

    <div class="alert alert-info">
      <span>·</span>
      <div>浮动奖（一/二等）按示意金额估算；实际以官方兑奖为准。</div>
    </div>

    <div class="card mb-4">
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">彩种</label>
          <select v-model="lotteryType" class="form-select" @change="fillLatest">
            <option v-for="(name, key) in TYPE_NAMES" :key="key" :value="key">{{ name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">倍数</label>
          <input v-model.number="multiple" type="number" min="1" class="form-input" />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">投注号码（主号空格，| 后为特别号）</label>
        <input v-model="betText" class="form-input" placeholder="03 12 18 22 27 31 | 09" />
      </div>
      <div class="form-group">
        <label class="form-label">开奖号码</label>
        <input v-model="drawText" class="form-input" placeholder="自动填入最新一期，可改" />
      </div>
      <button class="btn btn-primary" type="button" @click="calc">计算</button>
    </div>

    <div v-if="result" class="card">
      <div class="card-title">结果 <span class="sub">{{ TYPE_NAMES[result.lottery_type] }}</span></div>
      <div class="grid grid-3 mb-4">
        <div class="stat">
          <div class="stat-label">奖级</div>
          <div class="stat-value" style="font-size:1.05rem">{{ result.level }}</div>
        </div>
        <div class="stat">
          <div class="stat-label">估算奖金</div>
          <div class="stat-value gold">¥ {{ result.amount }}</div>
        </div>
        <div class="stat">
          <div class="stat-label">命中</div>
          <div class="stat-value">主 {{ result.main_hit }} / 特 {{ result.special_hit }}</div>
        </div>
      </div>
      <div class="prize-hits" :class="{ empty: !hitView.hasHit }">
        <div class="prize-hits-label">命中号码<span v-if="hitView.hasHit"> · {{ hitView.count }}</span></div>
        <NumberBalls
          v-if="hitView.hasHit"
          :numbers="hitView.hits"
          :type="result.lottery_type"
          size="xl"
        />
        <div v-else class="prize-hits-empty">没有命中的号码</div>
      </div>
      <div class="mb-3">
        <div class="text-xs text-muted mb-2">投注 <span class="prize-legend">亮圈为命中</span></div>
        <NumberBalls :numbers="result.bet" :type="result.lottery_type" :marks="hitView.betMarks" />
      </div>
      <div>
        <div class="text-xs text-muted mb-2">开奖</div>
        <NumberBalls :numbers="result.draw" :type="result.lottery_type" :marks="hitView.drawMarks" />
      </div>
      <p class="text-xs text-muted mt-4">{{ result.note }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, TYPE_NAMES } from '../api'
import NumberBalls from '../components/NumberBalls.vue'

const lotteryType = ref('ssq')
const multiple = ref(1)
const betText = ref('03 12 18 22 27 31 | 09')
const drawText = ref('')
const result = ref(null)
const latestMap = ref({})

const SET_MATCH = new Set(['ssq', 'dlt', 'kl8'])
const GROUP_MATCH = new Set(['fc3d', 'pl3'])

function sameMultiset(a, b) {
  if (a.length !== b.length) return false
  return [...a].sort().join('\0') === [...b].sort().join('\0')
}

function markList(type, mine, other, pool) {
  const nums = mine || []
  const against = other || []
  if (SET_MATCH.has(type)) {
    const counts = new Map()
    for (const n of against) counts.set(n, (counts.get(n) || 0) + 1)
    return nums.map((n) => {
      const left = counts.get(n) || 0
      if (!left) return false
      counts.set(n, left - 1)
      return true
    })
  }
  if (GROUP_MATCH.has(type) && pool === 'main') {
    const a = nums.slice(0, 3)
    const b = against.slice(0, 3)
    if (a.length === 3 && sameMultiset(a, b)) return nums.map((_, i) => i < 3)
  }
  return nums.map((n, i) => against[i] === n)
}

const hitView = computed(() => {
  const r = result.value
  const bet = r?.bet || { main: [], special: [] }
  const draw = r?.draw || { main: [], special: [] }
  const type = r?.lottery_type
  const betMarks = {
    main: markList(type, bet.main, draw.main, 'main'),
    special: markList(type, bet.special, draw.special, 'special'),
  }
  const drawMarks = {
    main: markList(type, draw.main, bet.main, 'main'),
    special: markList(type, draw.special, bet.special, 'special'),
  }
  const hits = {
    main: (bet.main || []).filter((_, i) => betMarks.main[i]),
    special: (bet.special || []).filter((_, i) => betMarks.special[i]),
  }
  const count = hits.main.length + hits.special.length
  return { betMarks, drawMarks, hits, count, hasHit: count > 0 }
})

function parse(text) {
  const parts = text.split('|')
  return {
    main: (parts[0] || '').trim().split(/[\s,]+/).filter(Boolean),
    special: (parts[1] || '').trim().split(/[\s,]+/).filter(Boolean),
  }
}

function fmt(nums) {
  const m = (nums.main || []).join(' ')
  const s = (nums.special || []).join(' ')
  return s ? `${m} | ${s}` : m
}

function fillLatest() {
  const d = latestMap.value[lotteryType.value]
  if (d) drawText.value = fmt(d.numbers)
}

async function calc() {
  try {
    result.value = await api.prizeCalc({
      lottery_type: lotteryType.value,
      bet_numbers: parse(betText.value),
      draw_numbers: parse(drawText.value),
      multiple: multiple.value,
    })
  } catch (e) {
    alert(e.message)
  }
}

onMounted(async () => {
  const res = await api.latest()
  for (const item of res.items || []) latestMap.value[item.lottery_type] = item
  fillLatest()
})
</script>
