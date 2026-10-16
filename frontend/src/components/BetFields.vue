<template>
  <div class="bet-layout">
    <div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">玩法</label>
          <select class="form-select" :value="playState.play" @change="patch({ play: $event.target.value })">
            <option v-for="item in plays" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
          <p v-if="currentPlay" class="form-hint">{{ currentPlay.hint }}</p>
        </div>
        <div v-if="currentPlay?.picks" class="form-group">
          <label class="form-label">选几</label>
          <select class="form-select" :value="playState.pick" @change="patch({ pick: Number($event.target.value) })">
            <option v-for="n in currentPlay.picks" :key="n" :value="n">选{{ pickLabel(n) }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">倍数</label>
          <input
            class="form-input"
            type="number"
            min="1"
            :value="playState.multiple"
            @input="patch({ multiple: Math.max(1, Number($event.target.value) || 1) })"
          />
        </div>
      </div>

      <div v-if="positionInput" class="pos-inputs">
        <div v-for="(label, i) in positionInput.labels" :key="label" class="form-group">
          <label class="form-label">{{ label }}</label>
          <NumberPad
            :from="0"
            :to="positionTo(i)"
            :pad="1"
            :color="positionColor(i)"
            :max="positionMax"
            :selected="tokens(playState.positions[i], 1)"
            @update:selected="setPos(i, $event.join(' '))"
          />
        </div>
      </div>
      <div v-else-if="group3Pair" class="pos-inputs">
        <div class="form-group">
          <label class="form-label">重号</label>
          <NumberPad
            :from="0"
            :to="9"
            :pad="1"
            color="green"
            :max="1"
            :selected="group3Pair.pair ? [group3Pair.pair] : []"
            @update:selected="setGroup3($event[0] || '', group3Pair.single)"
          />
        </div>
        <div class="form-group">
          <label class="form-label">单号</label>
          <NumberPad
            :from="0"
            :to="9"
            :pad="1"
            color="green"
            :max="1"
            :selected="group3Pair.single ? [group3Pair.single] : []"
            @update:selected="setGroup3(group3Pair.pair, $event[0] || '')"
          />
        </div>
      </div>
      <template v-else>
        <div v-for="input in ballInputs" :key="input.key" class="form-group">
          <label class="form-label">{{ input.label }}</label>
          <NumberPad
            :from="poolOf(input.key).from"
            :to="poolOf(input.key).to"
            :pad="poolOf(input.key).pad"
            :color="poolOf(input.key).color"
            :max="limitOf(input.key).max"
            :min="limitOf(input.key).min"
            :selected="tokens(input.key === 'special' ? playState.specialText : playState.mainText, poolOf(input.key).pad)"
            @update:selected="setBalls(input.key, $event)"
          />
        </div>
      </template>

      <div v-if="hitView" class="prize-hits" :class="{ empty: !hitView.hasHit }">
        <div class="prize-hits-label">命中号码<span v-if="hitView.hasHit"> · {{ hitView.count }}</span></div>
        <NumberBalls v-if="hitView.hasHit" :numbers="hitView.hits" :type="lotteryType" size="xl" />
        <div v-else class="prize-hits-empty">没有命中的号码</div>
      </div>
      <div v-if="hitView" class="form-group">
        <div class="form-label">投注 <span class="prize-legend">亮圈为命中</span></div>
        <NumberBalls :numbers="hitView.betNumbers" :type="lotteryType" :marks="hitView.betMarks" />
      </div>
      <div v-if="hasDraw" class="form-group">
        <div class="form-label">{{ draw.issue ? `第 ${draw.issue} 期开奖` : '开奖号码' }}</div>
        <NumberBalls
          :numbers="hitView ? hitView.drawNumbers : draw.numbers"
          :type="lotteryType"
          :marks="hitView ? hitView.drawMarks : null"
          :size="hitView ? '' : 'sm'"
        />
      </div>
      <p v-else class="form-hint">{{ emptyDrawHint }}</p>

      <p v-if="error" class="bet-error">{{ error }}</p>
      <div v-else-if="result" class="stake-box">
        <div class="stake-line">{{ result.play_name }} · {{ result.bets }} 注 × {{ result.stake }} 元 × {{ result.multiple }} 倍 = ¥ {{ result.cost }}</div>
        <div class="stake-line">估算奖金 ¥ {{ result.amount }} · {{ result.level }}</div>
        <ul v-if="result.breakdown?.length" class="breakdown">
          <li v-for="row in result.breakdown" :key="row.condition + row.level">
            {{ row.condition }} {{ row.level }} × {{ row.count }} = ¥ {{ row.amount }}
            <span v-if="row.floating">（浮动示意）</span>
          </li>
        </ul>
        <p class="form-hint">{{ result.note }}</p>
      </div>
    </div>

    <div>
      <div class="card-title">奖金对照 <span class="sub">单注 {{ rules?.stake || 2 }} 元</span></div>
      <div class="table-wrap">
        <table class="prize-table">
          <thead>
            <tr><th>条件</th><th>奖级</th><th>单注奖金</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in table" :key="row.condition + row.level" :class="{ hit: hitKeys.has(row.condition + '|' + row.level) }">
              <td>{{ row.condition }}</td>
              <td>{{ row.level }}</td>
              <td class="mono">{{ row.amount_label }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="ruleNote" class="form-hint">{{ ruleNote }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import NumberBalls from './NumberBalls.vue'
import NumberPad from './NumberPad.vue'

const PICK = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

const props = defineProps({
  lotteryType: { type: String, required: true },
  playState: { type: Object, required: true },
  draw: { type: Object, default: null },
  emptyDrawHint: { type: String, default: '这一期还没有开奖记录，奖金先按 0。' },
})
const emit = defineEmits(['update:playState', 'result'])

const rules = ref(null)
const result = ref(null)
const error = ref('')
let timer = 0
let seq = 0

const spec = computed(() => rules.value?.lotteries?.[props.lotteryType] || null)
const plays = computed(() => spec.value?.plays || [])
const currentPlay = computed(() => plays.value.find((item) => item.id === props.playState.play) || plays.value[0] || null)
const positionInput = computed(() => (currentPlay.value?.inputs || []).find((item) => item.kind === 'positions') || null)
const ballInputs = computed(() => (currentPlay.value?.inputs || []).filter((item) => item.kind === 'balls'))
const ruleNote = computed(() => spec.value?.note || '')
const table = computed(() => {
  if (!spec.value) return []
  if (spec.value.tables) return spec.value.tables[String(props.playState.pick || 10)] || []
  return spec.value.table || []
})
const hasDraw = computed(() => {
  const numbers = props.draw?.numbers
  return Boolean(numbers?.main?.length || numbers?.special?.length || numbers?.positions?.length)
})
const hitKeys = computed(() => new Set((result.value?.breakdown || []).map((row) => row.condition + '|' + row.level)))
const hitView = computed(() => buildHitView(props.lotteryType, result.value))

function asList(value) {
  return Array.isArray(value) ? value.map((n) => String(n)) : []
}

function setFlags(mine, other) {
  const counts = new Map()
  for (const n of other) counts.set(n, (counts.get(n) || 0) + 1)
  return mine.map((n) => {
    const left = counts.get(n) || 0
    if (!left) return false
    counts.set(n, left - 1)
    return true
  })
}

function positionalDigits(type, draw) {
  const positions = draw?.positions || []
  if (positions.some((pos) => (pos || []).length)) {
    return positions.map((pos) => String((pos || [])[0] ?? ''))
  }
  if (type === 'qxc') return [...asList(draw?.main), ...asList(draw?.special)]
  return asList(draw?.main)
}

function buildHitView(type, res) {
  if (!res?.opened) return null
  const bet = res.bet || {}
  const draw = res.draw || {}
  const positions = Array.isArray(bet.positions) ? bet.positions : []
  if (positions.some((pos) => (pos || []).length)) {
    const digits = positionalDigits(type, draw)
    const betPos = positions.map((pos) => asList(pos))
    const betMarks = {
      positions: betPos.map((pos, i) => pos.map((n) => n === digits[i])),
    }
    const drawPositions = Array.isArray(draw.positions) ? draw.positions : []
    const drawHasPos = drawPositions.some((pos) => (pos || []).length)
    const specialIndex = type === 'qxc' ? betPos.length - 1 : -1
    const hitMain = []
    const hitSpecial = []
    betPos.forEach((pos, i) => {
      for (const n of pos) {
        if (n !== digits[i]) continue
        if (i === specialIndex) hitSpecial.push(n)
        else hitMain.push(n)
      }
    })
    const count = hitMain.length + hitSpecial.length
    return {
      hasHit: count > 0,
      count,
      hits: { main: hitMain, special: hitSpecial },
      betNumbers: { positions: betPos },
      betMarks,
      drawNumbers: drawHasPos
        ? { positions: drawPositions }
        : { main: asList(draw.main), special: asList(draw.special) },
      drawMarks: drawHasPos
        ? { positions: drawPositions.map((pos, i) => asList(pos).map((n) => (betPos[i] || []).includes(n))) }
        : {
            main: asList(draw.main).map((n, i) => (betPos[i] || []).includes(n)),
            special: asList(draw.special).map((n) => (type === 'qxc' ? (betPos[specialIndex] || []).includes(n) : false)),
          },
    }
  }

  const betMain = asList(bet.main)
  const betSpecial = asList(bet.special)
  const drawMain = asList(draw.main)
  const drawSpecial = asList(draw.special)
  const betMarks = { main: setFlags(betMain, drawMain), special: setFlags(betSpecial, drawSpecial) }
  const drawMarks = { main: setFlags(drawMain, betMain), special: setFlags(drawSpecial, betSpecial) }
  const hits = {
    main: betMain.filter((_, i) => betMarks.main[i]),
    special: betSpecial.filter((_, i) => betMarks.special[i]),
  }
  const count = hits.main.length + hits.special.length
  return {
    hasHit: count > 0,
    count,
    hits,
    betNumbers: { main: betMain, special: betSpecial },
    betMarks,
    drawNumbers: { main: drawMain, special: drawSpecial },
    drawMarks,
  }
}

function pickLabel(n) {
  return PICK[n] || n
}

function patch(partial) {
  emit('update:playState', { ...props.playState, ...partial })
}

const group3Pair = computed(() => {
  if (!['fc3d', 'pl3'].includes(props.lotteryType) || props.playState.play !== 'group3') return null
  const nums = split(props.playState.mainText)
  const counts = new Map()
  for (const n of nums) counts.set(n, (counts.get(n) || 0) + 1)
  const pair = [...counts.keys()].find((key) => counts.get(key) >= 2) || ''
  const single = [...counts.keys()].find((key) => key !== pair) || ''
  return { pair, single }
})

const positionMax = computed(() => (String(props.playState.play).includes('compound') ? 10 : 1))

function poolOf(key) {
  const pools = {
    ssq: { main: { from: 1, to: 33, pad: 2, color: 'red' }, special: { from: 1, to: 16, pad: 2, color: 'blue' } },
    dlt: { main: { from: 1, to: 35, pad: 2, color: 'red' }, special: { from: 1, to: 12, pad: 2, color: 'blue' } },
    kl8: { main: { from: 1, to: 80, pad: 2, color: 'orange' } },
    fc3d: { main: { from: 0, to: 9, pad: 1, color: 'green' } },
    pl3: { main: { from: 0, to: 9, pad: 1, color: 'green' } },
  }
  return pools[props.lotteryType]?.[key] || { from: 0, to: 9, pad: 1, color: 'green' }
}

function limitOf(key) {
  const play = props.playState.play
  const type = props.lotteryType
  if (type === 'ssq') {
    if (play === 'single') return key === 'main' ? { min: 6, max: 6 } : { min: 1, max: 1 }
    return key === 'main' ? { min: 6, max: 20 } : { min: 1, max: 16 }
  }
  if (type === 'dlt') {
    if (play === 'single') return key === 'main' ? { min: 5, max: 5 } : { min: 2, max: 2 }
    return key === 'main' ? { min: 5, max: 20 } : { min: 2, max: 12 }
  }
  if (type === 'kl8') {
    const pick = Number(props.playState.pick) || 1
    return { min: pick, max: 0 }
  }
  if (play === 'group6') return { min: 3, max: 3 }
  if (play === 'group6_compound' || play === 'group3_compound') return { min: play === 'group6_compound' ? 4 : 2, max: 10 }
  return { min: 0, max: 0 }
}

function positionTo(index) {
  if (props.lotteryType === 'qxc' && index === (positionInput.value?.labels.length || 1) - 1) return 14
  return 9
}

function positionColor(index) {
  if (props.lotteryType === 'qxc') {
    return index === (positionInput.value?.labels.length || 1) - 1 ? 'orange' : 'purple'
  }
  return 'green'
}

function tokens(text, pad) {
  return split(text).map((item) => {
    if (!/^\d+$/.test(item)) return item
    return pad > 1 ? String(Number(item)).padStart(pad, '0') : String(Number(item))
  })
}

function setBalls(key, list) {
  const text = list.join(' ')
  patch(key === 'special' ? { specialText: text } : { mainText: text })
}

function setGroup3(pair, single) {
  if (pair && single && pair === single) return
  const parts = []
  if (pair) parts.push(pair, pair)
  if (single) parts.push(single)
  patch({ mainText: parts.join(' ') })
}

function setPos(index, value) {
  const positions = (props.playState.positions || []).slice()
  while (positions.length <= index) positions.push('')
  positions[index] = value
  patch({ positions })
}

function split(text) {
  return String(text || '').trim().split(/[\s,]+/).filter(Boolean)
}

function hasInput() {
  if (positionInput.value) return (props.playState.positions || []).some((item) => String(item || '').trim())
  return String(props.playState.mainText || '').trim() || String(props.playState.specialText || '').trim()
}

function payload() {
  const state = props.playState
  return {
    play: state.play,
    pick: state.pick,
    multiple: state.multiple || 1,
    main: split(state.mainText),
    special: split(state.specialText),
    positions: positionInput.value ? (state.positions || []).map(split) : [],
  }
}

async function runCalc() {
  const current = ++seq
  if (!rules.value || !hasInput()) {
    result.value = null
    error.value = ''
    emit('result', null)
    return
  }
  try {
    const data = await api.prizeCalc({
      lottery_type: props.lotteryType,
      play: props.playState.play,
      pick: props.playState.pick,
      multiple: props.playState.multiple || 1,
      bet_numbers: payload(),
      draw_numbers: hasDraw.value ? props.draw.numbers : null,
    })
    if (current !== seq) return
    result.value = data
    error.value = ''
    emit('result', data)
  } catch (err) {
    if (current !== seq) return
    result.value = null
    error.value = err.message
    emit('result', null)
  }
}

function schedule() {
  clearTimeout(timer)
  timer = setTimeout(runCalc, 220)
}

watch(() => [props.lotteryType, props.playState, props.draw], schedule, { deep: true })

onMounted(async () => {
  rules.value = await api.prizeRules()
  schedule()
})
</script>
