<template>
  <div>
    <div class="page-header">
      <div>
        <h1>奖金计算</h1>
        <p>单式 / 复式 · 对照奖金表</p>
      </div>
    </div>

    <div class="alert alert-info">
      <span>·</span>
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, TYPE_NAMES } from '../api'
import BetFields from '../components/BetFields.vue'

const lotteryType = ref('ssq')
const drawText = ref('')
const result = ref(null)
const latestMap = ref({})
const bet = ref(defaultBet('ssq'))

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

watch(lotteryType, (next, prev) => {
  if (!prev || next === prev) return
  onTypeChange()
})

onMounted(async () => {
  const res = await api.latest()
  for (const item of res.items || []) latestMap.value[item.lottery_type] = item
  fillLatest()
})
</script>
