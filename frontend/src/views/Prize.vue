<template>
  <div>
    <div class="page-header">
      <div>
        <h1>奖金计算</h1>
        <p>单式 / 复式 · 对照奖金表</p>
      </div>
    </div>

    <div class="alert alert-info">
      <AppIcon name="info" :size="14" style="margin-top:2px;flex:none" />
      <div>浮动奖按示意金额估算；固定奖按公开规则。实际以官方兑奖为准。</div>
    </div>

    <div class="card">
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">彩种</label>
          <select v-model="lotteryType" class="form-select">
            <option v-for="(name, key) in TYPE_NAMES" :key="key" :value="key">{{ name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">开奖号码（主号空格，| 后为特别号）</label>
          <input v-model="drawText" class="form-input mono" placeholder="留空则只算注数" />
          <p v-if="latestDraw" class="form-hint">
            最新期 {{ latestDraw.issue }}
            <button class="text-btn" type="button" @click="fillLatest">填入开奖号</button>
          </p>
        </div>
      </div>
      <BetFields
        :lottery-type="lotteryType"
        :play-state="bet"
        :draw="drawProp"
        empty-draw-hint="填写开奖号码后，会按右侧奖金表估算中奖金额。"
        @update:play-state="bet = $event"
        @result="result = $event"
      />
    </div>

    <div class="card mt-4">
      <div class="card-title">
        历史回测
        <span class="sub">用当前号码对照本地开奖 · 示意奖金 · 不写入账本</span>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">样本</label>
          <select v-model.number="backLimit" class="form-select">
            <option :value="20">近 20 期</option>
            <option :value="30">近 30 期</option>
            <option :value="50">近 50 期</option>
            <option :value="100">近 100 期</option>
          </select>
        </div>
        <div class="form-group predict-actions">
          <button class="btn btn-primary" type="button" :disabled="!result || backtesting" @click="runBacktest">
            <AppIcon v-if="backtesting" name="sync" :size="14" class="spin" />
            {{ backtesting ? '回测中…' : '开始回测' }}
          </button>
        </div>
      </div>
      <p class="form-hint">先填好上面的投注号码。回测只读本地开奖，不改变奖金计算。</p>
      <p v-if="backError" class="bet-error">{{ backError }}</p>
      <template v-if="backtest">
        <div class="grid grid-4 mt-3">
          <div class="card stat">
            <div class="stat-label">样本期数</div>
            <div class="stat-value">{{ backtest.sample_size }}</div>
          </div>
          <div class="card stat">
            <div class="stat-label">示意中奖</div>
            <div class="stat-value">{{ backtest.win_count }}</div>
          </div>
          <div class="card stat">
            <div class="stat-label">示意奖金</div>
            <div class="stat-value ok">¥ {{ backtest.illustrative_amount }}</div>
          </div>
          <div class="card stat">
            <div class="stat-label">示意盈亏</div>
            <div class="stat-value" :class="backtest.illustrative_net >= 0 ? 'ok' : 'danger'">
              ¥ {{ backtest.illustrative_net }}
            </div>
          </div>
        </div>
        <div v-if="backtest.hits.length" class="table-wrap mt-3">
          <table>
            <thead><tr><th>期号</th><th>奖级</th><th>主号命中</th><th>特别号</th><th>示意金额</th></tr></thead>
            <tbody>
              <tr v-for="hit in backtest.hits" :key="hit.issue">
                <td class="mono">{{ hit.issue }}</td>
                <td>{{ hit.level }}</td>
                <td class="mono">{{ hit.main_hit }}</td>
                <td class="mono">{{ hit.special_hit }}</td>
                <td class="mono">{{ hit.amount }}<span v-if="hit.floating" class="text-xs text-muted"> 浮动</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="text-xs text-muted mt-3">这几期没有示意中奖。</p>
        <p class="text-xs text-muted mt-3">{{ backtest.disclaimer }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, TYPE_NAMES } from '../api'
import BetFields from '../components/BetFields.vue'
import AppIcon from '../components/AppIcon.vue'

const lotteryType = ref('ssq')
const drawText = ref('')
const result = ref(null)
const latestMap = ref({})
const bet = ref(defaultBet('ssq'))
const backLimit = ref(30)
const backtest = ref(null)
const backtesting = ref(false)
const backError = ref('')

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

function fmt(nums) {
  if (!nums) return ''
  if (nums.positions?.some((pos) => (pos || []).length)) {
    return nums.positions.map((pos) => (pos || []).join(' ')).join(' | ')
  }
  const main = (nums.main || []).join(' ')
  const special = (nums.special || []).join(' ')
  return special ? `${main} | ${special}` : main
}

function parse(text) {
  const parts = String(text || '').split('|')
  return {
    main: (parts[0] || '').trim().split(/[\s,]+/).filter(Boolean),
    special: (parts[1] || '').trim().split(/[\s,]+/).filter(Boolean),
  }
}

const latestDraw = computed(() => latestMap.value[lotteryType.value] || null)
const drawProp = computed(() => {
  const numbers = parse(drawText.value)
  if (!numbers.main.length && !numbers.special.length) return null
  return { issue: latestDraw.value?.issue || '', numbers }
})

function fillLatest() {
  const row = latestMap.value[lotteryType.value]
  if (row) drawText.value = fmt(row.numbers)
}

function onTypeChange() {
  bet.value = defaultBet(lotteryType.value)
  fillLatest()
}

const betKey = computed(() => {
  if (!result.value?.bet) return ''
  return JSON.stringify({
    play: result.value.play,
    pick: result.value.pick,
    multiple: result.value.multiple,
    bet: result.value.bet,
  })
})
let backSeq = 0

watch(lotteryType, (next, prev) => {
  if (!prev || next === prev) return
  onTypeChange()
})

watch(betKey, () => {
  backSeq += 1
  backtest.value = null
  backError.value = ''
})

async function runBacktest() {
  if (!result.value?.bet) return
  const seq = ++backSeq
  backtesting.value = true
  backError.value = ''
  try {
    const data = await api.backtest({
      lottery_type: lotteryType.value,
      bet_numbers: result.value.bet,
      play: result.value.play,
      pick: result.value.pick,
      multiple: result.value.multiple,
      limit: backLimit.value,
    })
    if (seq !== backSeq) return
    backtest.value = data
  } catch (e) {
    if (seq !== backSeq) return
    backtest.value = null
    backError.value = e.message
  } finally {
    if (seq === backSeq) backtesting.value = false
  }
}

onMounted(async () => {
  const res = await api.latest()
  for (const item of res.items || []) latestMap.value[item.lottery_type] = item
  fillLatest()
})
</script>
