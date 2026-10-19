<template>
  <div id="bet-expander" class="card mb-4">
    <div class="card-title">
      复式 / 胆拖
      <span class="sub">展开成单注 · 2 元/注</span>
    </div>
    <p class="strategy-desc">按这个彩种的区号规则，把复式或多出来的胆拖拆成单注，马上看注数和金额。可以放进选号篮。不是推荐，也不预测开奖。</p>

    <p v-if="rulesError" class="form-hint expand-error">{{ rulesError }}</p>
    <div v-else-if="!game" class="loading-line"><AppIcon name="sync" :size="15" class="spin" />加载规则…</div>
    <template v-else>
      <div class="chip-row compact">
        <button type="button" class="chip" :class="{ active: mode === 'compound' }" @click="mode = 'compound'">复式</button>
        <button type="button" class="chip" :class="{ active: mode === 'banker' }" :disabled="bankerOff" @click="chooseBanker">胆拖</button>
        <button type="button" class="chip" :class="{ active: onlyCenter }" @click="onlyCenter = !onlyCenter">只留常见带</button>
      </div>
      <p v-if="mode === 'banker'" class="form-hint">胆码每注都有，拖码用来补齐。同一区的胆码和拖码不能重复。</p>
      <p v-else class="form-hint">号码多过单注所需，就按组合展开。个数刚好时是 1 注。</p>
      <p v-if="onlyCenter" class="form-hint">只留下主号和值、跨度、奇数个数都落在历史 p25–p75 的单注。没有开奖样本时不过滤。</p>

      <div v-if="game.pick_min" class="chip-row compact">
        <button
          v-for="n in pickChoices"
          :key="n"
          type="button"
          class="chip"
          :class="{ active: pick === n }"
          @click="pick = n"
        >选{{ PICK_CN[n] }}</button>
      </div>

      <template v-if="game.kind === 'set'">
        <div v-for="zone in game.zones" :key="zone.key" class="expand-zone">
          <div class="form-label">{{ zone.label }}</div>
          <p class="form-hint">{{ zoneHint(zone) }}</p>
          <template v-if="mode === 'compound' || !zone.banker">
            <NumberPad
              :from="zone.lo"
              :to="zone.hi"
              :pad="zone.width"
              :color="zone.color"
              :min="needOf(zone)"
              :max="zone.max"
              :selected="zoneSlot(zone.key).numbers"
              @update:selected="(values) => setList(zone.key, 'numbers', values)"
            />
            <input
              v-model="drafts[draftId(zone.key, 'numbers')]"
              class="form-input expand-paste"
              :placeholder="`${zone.label}，如 03 07，回车填入`"
              @keydown.enter.prevent="applyPaste(zone, 'numbers')"
            />
          </template>
          <div v-else class="expand-zone-grid">
            <div>
              <div class="form-label">胆码</div>
              <NumberPad
                :from="zone.lo"
                :to="zone.hi"
                :pad="zone.width"
                :color="zone.color"
                :max="bankerMax(zone)"
                :selected="zoneSlot(zone.key).bankers"
                @update:selected="(values) => setBankers(zone.key, values)"
              />
              <input
                v-model="drafts[draftId(zone.key, 'bankers')]"
                class="form-input expand-paste"
                placeholder="胆码，回车填入"
                @keydown.enter.prevent="applyPaste(zone, 'bankers')"
              />
            </div>
            <div>
              <div class="form-label">拖码</div>
              <NumberPad
                :from="zone.lo"
                :to="zone.hi"
                :pad="zone.width"
                :color="zone.color"
                :min="2"
                :max="dragMax(zone)"
                :exclude="zoneSlot(zone.key).bankers"
                :selected="zoneSlot(zone.key).drags"
                @update:selected="(values) => setList(zone.key, 'drags', values, zone)"
              />
              <input
                v-model="drafts[draftId(zone.key, 'drags')]"
                class="form-input expand-paste"
                placeholder="拖码，回车填入"
                @keydown.enter.prevent="applyPaste(zone, 'drags')"
              />
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div v-for="(pos, index) in game.positions" :key="pos.key" class="expand-zone">
          <div class="form-label">{{ pos.label }}</div>
          <p class="form-hint">{{ posHint(pos) }}</p>
          <template v-if="mode === 'compound'">
            <NumberPad
              :from="pos.lo"
              :to="pos.hi"
              :pad="pos.width"
              :color="pos.color"
              :min="1"
              :max="pos.max"
              :selected="positionSlot(index).numbers"
              @update:selected="(values) => setPosition(index, 'numbers', values)"
            />
            <input
              v-model="drafts[draftId('p' + index, 'numbers')]"
              class="form-input expand-paste"
              placeholder="数字，回车填入"
              @keydown.enter.prevent="applyPaste(pos, 'numbers', index)"
            />
          </template>
          <div v-else class="expand-zone-grid">
            <div>
              <div class="form-label">胆码</div>
              <NumberPad
                :from="pos.lo"
                :to="pos.hi"
                :pad="pos.width"
                :color="pos.color"
                :max="1"
                :selected="positionSlot(index).bankers"
                @update:selected="(values) => setPositionBankers(index, values)"
              />
            </div>
            <div>
              <div class="form-label">拖码</div>
              <NumberPad
                :from="pos.lo"
                :to="pos.hi"
                :pad="pos.width"
                :color="pos.color"
                :max="pos.max"
                :exclude="positionSlot(index).bankers"
                :selected="positionSlot(index).drags"
                @update:selected="(values) => setPosition(index, 'drags', values)"
              />
            </div>
          </div>
        </div>
      </template>

      <div class="expand-summary">
        <strong v-if="result && (result.valid || result.bet_count)">{{ result.bet_count }} 注 · {{ result.cost }} 元</strong>
        <strong v-else>选号后显示注数</strong>
        <span v-if="result && result.matched != null" class="form-hint">常见带留下 {{ result.matched }} 注</span>
        <span v-if="loading" class="form-hint">计算中…</span>
      </div>
      <p v-for="message in result?.messages || []" :key="message" class="form-hint expand-error">{{ message }}</p>
      <p v-for="note in result?.notes || []" :key="note" class="form-hint">{{ note }}</p>
      <div v-if="result?.warnings?.length" class="alert alert-warn mb-4">
        <AppIcon name="alert" :size="14" style="margin-top:2px;flex:none" />
        <div>{{ result.warnings.join(' ') }}</div>
      </div>

      <div v-if="pages.length" class="expand-list">
        <label v-for="ticket in pages" :key="ticketKey(ticket)" class="expand-ticket">
          <input type="checkbox" :checked="!!checked[ticketKey(ticket)]" @change="toggle(ticket)" />
          <NumberBalls :numbers="ticket" :type="lotteryType" size="sm" />
        </label>
      </div>
      <div class="form-actions">
        <button v-if="result?.has_more" class="btn btn-ghost btn-sm" type="button" :disabled="loading" @click="more">再看 {{ pageSize }} 注</button>
        <button class="btn btn-primary btn-sm" type="button" :disabled="!pages.length" @click="addTickets">{{ addLabel }}</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="clearCurrent">清空选号</button>
      </div>
      <p class="form-hint">{{ rules.disclaimer }}</p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import NumberPad from './NumberPad.vue'
import NumberBalls from './NumberBalls.vue'
import AppIcon from './AppIcon.vue'
import { toast } from '../composables/feedback'
import { useBasket } from '../composables/useBasket'
import { basketDrafts, parseBalls, ticketKey } from '../lib/betExpand'

const PICK_CN = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

const props = defineProps({
  lotteryType: { type: String, required: true },
})

const basket = useBasket()
const rules = ref(null)
const rulesError = ref('')
const mode = ref('compound')
const pick = ref(5)
const onlyCenter = ref(false)
const loading = ref(false)
const result = ref(null)
const pages = ref([])
const checked = reactive({})
const drafts = reactive({})
const selections = reactive({})

const game = computed(() => rules.value?.games?.[props.lotteryType] || null)
const pickChoices = computed(() => {
  const current = game.value
  if (!current?.pick_min) return []
  const list = []
  for (let n = current.pick_min; n <= current.pick_max; n += 1) list.push(n)
  return list
})
const bankerOff = computed(() => Boolean(game.value?.pick_min) && pick.value < 2)
const pageSize = computed(() => rules.value?.page_size || 60)
const chosen = computed(() => pages.value.filter((ticket) => checked[ticketKey(ticket)]))
const addLabel = computed(() => {
  if (chosen.value.length) return `加入所选 ${chosen.value.length} 注`
  if (pages.value.length) return `加入已展开 ${pages.value.length} 注`
  return '加入选号篮'
})

let timer = null
let seq = 0

function blankSelection(current) {
  const zones = {}
  for (const zone of current?.zones || []) zones[zone.key] = { numbers: [], bankers: [], drags: [] }
  const positions = (current?.positions || []).map(() => ({ numbers: [], bankers: [], drags: [] }))
  return { zones, positions }
}

function ensure(type) {
  const current = rules.value?.games?.[type]
  if (!current) return null
  if (!selections[type] || (current.kind === 'digit' && selections[type].positions.length !== current.positions.length)) {
    selections[type] = blankSelection(current)
  }
  return selections[type]
}

function current() {
  return ensure(props.lotteryType) || { zones: {}, positions: [] }
}

function zoneSlot(key) {
  return current().zones[key]
}

function bankerMax(zone) {
  return Math.max(1, needOf(zone) - 1)
}

function positionSlot(index) {
  return current().positions[index]
}

function needOf(zone) {
  return zone.pick || pick.value
}

function dragMax(zone) {
  return Math.max(2, zone.max - zoneSlot(zone.key).bankers.length)
}

function zoneHint(zone) {
  const need = needOf(zone)
  if (mode.value === 'banker' && zone.banker) {
    return `胆码 1–${Math.max(1, need - 1)} 个，拖码至少 2 个，合计至少 ${need + 1} 个，最多 ${zone.max} 个`
  }
  return `选 ${need}–${zone.max} 个，每注取 ${need} 个`
}

function posHint(pos) {
  if (mode.value === 'banker') return '胆码锁定这一位；不锁时在拖码里选候选'
  return `这一位选 1–${pos.max} 个数字`
}

function draftId(key, field) {
  return `${props.lotteryType}:${mode.value}:${key}:${field}`
}

function chosenTickets() {
  return chosen.value.length ? chosen.value : pages.value
}

function hasAny(sel, current) {
  if (!sel || !current) return false
  if (current.kind === 'digit') {
    return sel.positions.some((item) => item.numbers.length || item.bankers.length || item.drags.length)
  }
  return Object.values(sel.zones).some((item) => item.numbers.length || item.bankers.length || item.drags.length)
}

function payload(offset) {
  const currentGame = game.value
  const sel = current()
  const body = {
    lottery_type: props.lotteryType,
    mode: mode.value,
    offset,
    limit: pageSize.value,
    only_center: onlyCenter.value,
  }
  if (currentGame.pick_min) body.pick = pick.value
  if (currentGame.kind === 'digit') {
    body.positions = sel.positions.map((item) => (
      mode.value === 'compound'
        ? { numbers: item.numbers }
        : { bankers: item.bankers, drags: item.drags }
    ))
  } else {
    for (const zone of currentGame.zones) {
      const item = sel.zones[zone.key]
      body[zone.key] = mode.value === 'banker' && zone.banker
        ? { bankers: item.bankers, drags: item.drags }
        : { numbers: item.numbers }
    }
  }
  return body
}

function resetChecks() {
  for (const key of Object.keys(checked)) delete checked[key]
}

async function load(reset) {
  const currentGame = game.value
  const sel = selections[props.lotteryType]
  if (!currentGame || !hasAny(sel, currentGame)) {
    result.value = null
    pages.value = []
    resetChecks()
    loading.value = false
    return
  }
  const token = ++seq
  const offset = reset ? 0 : pages.value.length
  loading.value = true
  try {
    const data = await api.betExpand(payload(offset))
    if (token !== seq) return
    result.value = data
    if (reset) {
      pages.value = data.tickets || []
      resetChecks()
    } else {
      pages.value = pages.value.concat(data.tickets || [])
    }
  } catch (err) {
    if (token !== seq) return
    result.value = {
      valid: false,
      bet_count: 0,
      cost: 0,
      messages: [err.message || '展开失败'],
      notes: [],
      warnings: [],
      tickets: [],
      has_more: false,
    }
    if (reset) pages.value = []
  } finally {
    if (token === seq) loading.value = false
  }
}

function schedule() {
  clearTimeout(timer)
  timer = setTimeout(() => load(true), 100)
}

function more() {
  load(false)
}

function chooseBanker() {
  if (bankerOff.value) return
  mode.value = 'banker'
}

function setList(key, field, values, zone = null) {
  const item = zoneSlot(key)
  if (field === 'drags') {
    const banned = new Set(item.bankers)
    const max = zone ? dragMax(zone) : values.length
    item.drags = values.filter((n) => !banned.has(n)).slice(0, max)
    return
  }
  item[field] = values
}

function setBankers(key, values) {
  const item = zoneSlot(key)
  item.bankers = values
  const zone = game.value.zones.find((entry) => entry.key === key)
  const max = zone ? Math.max(0, zone.max - values.length) : item.drags.length
  item.drags = item.drags.filter((n) => !values.includes(n)).slice(0, max)
}

function setPosition(index, field, values) {
  const item = positionSlot(index)
  if (field === 'drags') {
    const banned = new Set(item.bankers)
    item.drags = values.filter((n) => !banned.has(n))
    if (item.bankers.length) item.drags = []
    return
  }
  item[field] = values
}

function setPositionBankers(index, values) {
  const item = positionSlot(index)
  item.bankers = values.slice(0, 1)
  if (item.bankers.length) item.drags = []
}

function applyPaste(zone, field, positionIndex = null) {
  const id = draftId(positionIndex == null ? zone.key : `p${positionIndex}`, field)
  let max = zone.max
  if (field === 'bankers') max = positionIndex == null ? bankerMax(zone) : 1
  else if (field === 'drags') max = positionIndex == null ? dragMax(zone) : zone.max
  const { balls, invalid } = parseBalls(drafts[id], zone, max)
  if (positionIndex == null) {
    if (field === 'bankers') setBankers(zone.key, balls)
    else setList(zone.key, field, balls, zone)
  } else if (field === 'bankers') {
    setPositionBankers(positionIndex, balls)
  } else {
    setPosition(positionIndex, field, balls)
  }
  drafts[id] = ''
  if (invalid.length) toast(`号码超出范围：${invalid.join('、')}`, 'error')
}

function toggle(ticket) {
  const key = ticketKey(ticket)
  checked[key] = !checked[key]
}

function addTickets() {
  const tickets = chosenTickets()
  if (!tickets.length) return
  const outcome = basket.addMany(basketDrafts(props.lotteryType, tickets))
  if (outcome.added) {
    const extra = outcome.duplicates ? `，${outcome.duplicates} 注已在篮里` : ''
    toast(`已放入选号篮 ${outcome.added} 注${extra}`, 'ok')
    return
  }
  if (outcome.duplicates) toast('这些单注已经在选号篮里', 'info')
  else toast(outcome.invalid?.[0] || '没有放进去', 'error')
}

function clearCurrent() {
  selections[props.lotteryType] = blankSelection(game.value)
  result.value = null
  pages.value = []
  resetChecks()
}

async function loadRules() {
  rulesError.value = ''
  try {
    rules.value = await api.betExpandRules()
    ensure(props.lotteryType)
    schedule()
  } catch (err) {
    rulesError.value = err.message || '规则加载失败'
  }
}

watch(() => props.lotteryType, () => {
  if (rules.value) ensure(props.lotteryType)
  schedule()
})
watch([mode, pick, onlyCenter], () => schedule())
watch(pick, (value) => {
  if (value < 2 && mode.value === 'banker' && game.value?.pick_min) mode.value = 'compound'
})
watch(selections, () => schedule(), { deep: true })

onMounted(loadRules)
onUnmounted(() => clearTimeout(timer))
</script>
