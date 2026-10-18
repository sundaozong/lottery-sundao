<template>
  <div>
    <div class="page-header">
      <div>
        <h1>预测 / 推荐</h1>
        <p>策略生成号码 · 不保证任何中奖可能</p>
      </div>
    </div>

    <div class="alert alert-disclaimer">
      <AppIcon name="info" :size="14" style="margin-top:2px;flex:none" />
      <div>
        <strong>仅供娱乐。</strong>冷热、随机、混合与脉动综合均基于历史样本的统计玩具，
        <strong>不构成投注建议</strong>，亦不保证中奖。请理性购彩，量力而行。
      </div>
    </div>

    <div class="predict-layout">
      <div class="predict-main">
        <div class="card mb-4">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">彩种</label>
              <select v-model="lotteryType" class="form-select">
                <option v-for="(name, key) in TYPE_NAMES" :key="key" :value="key">{{ name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">策略</label>
              <select v-model="strategy" class="form-select">
                <option value="hot">热号加权</option>
                <option value="cold">冷号加权</option>
                <option value="hybrid">冷热混合</option>
                <option value="random">纯随机</option>
                <option value="pulse">脉动综合</option>
              </select>
              <p class="strategy-desc">{{ strategyHint }}</p>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">组数</label>
              <input v-model.number="count" class="form-input" type="number" min="1" max="10" />
            </div>
            <div class="form-group predict-actions">
              <button class="btn btn-primary" type="button" :disabled="loading" @click="run">
                <AppIcon v-if="loading" name="sync" :size="14" class="spin" />
                {{ loading ? (strategy === 'pulse' ? '综合打分中…' : '生成中…') : '生成推荐' }}
              </button>
              <button
                class="btn btn-ghost"
                type="button"
                :disabled="!result || mailing"
                @click="sendMail"
              >
                {{ mailing ? '发送中…' : '发送邮件' }}
              </button>
            </div>
          </div>
          <p v-if="mailMsg" class="form-hint mt-2">{{ mailMsg }}</p>
        </div>

        <div class="card mb-4">
          <div class="card-title">
            机选条件
            <span class="sub">{{ strategy === 'pulse' ? '脉动综合不套用' : '留空则按策略抽样' }}</span>
          </div>
          <p v-if="strategy === 'pulse'" class="strategy-desc">脉动综合仍按现有打分排序。机选条件只用于热号、冷号、混合和随机。</p>
          <template v-else>
            <p class="strategy-desc">胆码必出、杀号必不出。数字彩按各位计奇偶、和值与跨度，重复保留；乐透按号码集合。未填的条件不生效。</p>
            <div class="chip-row compact">
              <button type="button" class="chip" :class="{ active: oddBalanced }" @click="toggleOddBalance">奇偶接近</button>
              <button
                v-if="!lotteryMeta.digit"
                type="button"
                class="chip"
                :class="{ active: String(constraints.max_consecutive) === '2' }"
                @click="toggleConsecutive"
              >连号≤2</button>
              <button type="button" class="chip" @click="clearConstraints">清空条件</button>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">主号胆码</label>
                <div class="constraint-draft">
                  <input
                    v-model="drafts.includeMain"
                    class="form-input"
                    :placeholder="numberPlaceholder"
                    @keydown.enter.prevent="addNumbers('include_main', 'includeMain')"
                  />
                  <button class="btn btn-ghost" type="button" @click="addNumbers('include_main', 'includeMain')">加入</button>
                </div>
                <div v-if="constraints.include_main.length" class="chip-row compact constraint-chip-row">
                  <button
                    v-for="num in constraints.include_main"
                    :key="'in-' + num"
                    type="button"
                    class="chip active"
                    @click="removeNumber('include_main', num)"
                  >{{ num }} ×</button>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">主号杀号</label>
                <div class="constraint-draft">
                  <input
                    v-model="drafts.excludeMain"
                    class="form-input"
                    :placeholder="numberPlaceholder"
                    @keydown.enter.prevent="addNumbers('exclude_main', 'excludeMain')"
                  />
                  <button class="btn btn-ghost" type="button" @click="addNumbers('exclude_main', 'excludeMain')">加入</button>
                </div>
                <div v-if="constraints.exclude_main.length" class="chip-row compact constraint-chip-row">
                  <button
                    v-for="num in constraints.exclude_main"
                    :key="'ex-' + num"
                    type="button"
                    class="chip active"
                    @click="removeNumber('exclude_main', num)"
                  >{{ num }} ×</button>
                </div>
              </div>
            </div>
            <div v-if="lotteryMeta.special" class="form-row">
              <div class="form-group">
                <label class="form-label">特别号胆码</label>
                <div class="constraint-draft">
                  <input
                    v-model="drafts.includeSpecial"
                    class="form-input"
                    placeholder="特别号，回车加入"
                    @keydown.enter.prevent="addNumbers('include_special', 'includeSpecial')"
                  />
                  <button class="btn btn-ghost" type="button" @click="addNumbers('include_special', 'includeSpecial')">加入</button>
                </div>
                <div v-if="constraints.include_special.length" class="chip-row compact constraint-chip-row">
                  <button
                    v-for="num in constraints.include_special"
                    :key="'sin-' + num"
                    type="button"
                    class="chip active"
                    @click="removeNumber('include_special', num)"
                  >{{ num }} ×</button>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">特别号杀号</label>
                <div class="constraint-draft">
                  <input
                    v-model="drafts.excludeSpecial"
                    class="form-input"
                    placeholder="特别号，回车加入"
                    @keydown.enter.prevent="addNumbers('exclude_special', 'excludeSpecial')"
                  />
                  <button class="btn btn-ghost" type="button" @click="addNumbers('exclude_special', 'excludeSpecial')">加入</button>
                </div>
                <div v-if="constraints.exclude_special.length" class="chip-row compact constraint-chip-row">
                  <button
                    v-for="num in constraints.exclude_special"
                    :key="'sex-' + num"
                    type="button"
                    class="chip active"
                    @click="removeNumber('exclude_special', num)"
                  >{{ num }} ×</button>
                </div>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">奇数个数</label>
                <div class="form-row">
                  <input v-model="constraints.odd_min" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="最少" />
                  <input v-model="constraints.odd_max" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="最多" />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">和值范围</label>
                <div class="form-row">
                  <input v-model="constraints.sum_min" class="form-input" type="number" placeholder="最低" />
                  <input v-model="constraints.sum_max" class="form-input" type="number" placeholder="最高" />
                </div>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">跨度范围</label>
                <div class="form-row">
                  <input v-model="constraints.span_min" class="form-input" type="number" min="0" placeholder="最小" />
                  <input v-model="constraints.span_max" class="form-input" type="number" min="0" placeholder="最大" />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">大号个数</label>
                <div class="form-row">
                  <input v-model="constraints.big_min" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="最少" />
                  <input v-model="constraints.big_max" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="最多" />
                </div>
                <p class="form-hint">{{ bigHint }}</p>
              </div>
            </div>
            <div class="form-row">
              <div v-if="!lotteryMeta.digit" class="form-group">
                <label class="form-label">最长连号</label>
                <input v-model="constraints.max_consecutive" class="form-input" type="number" min="1" :max="lotteryMeta.need" placeholder="不限" />
              </div>
              <div class="form-group">
                <label class="form-label">三区个数</label>
                <div class="form-row" style="grid-template-columns: repeat(3, 1fr)">
                  <input v-model="constraints.zone1" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="一区" />
                  <input v-model="constraints.zone2" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="二区" />
                  <input v-model="constraints.zone3" class="form-input" type="number" min="0" :max="lotteryMeta.need" placeholder="三区" />
                </div>
                <p class="form-hint">{{ zoneHint }}</p>
              </div>
            </div>
          </template>
        </div>

        <div v-if="result" class="card mb-4">
          <div class="card-title">
            推荐方案
            <span class="sub">{{ TYPE_NAMES[result.lottery_type] || result.lottery_type }} · {{ strategyName(result.strategy) }}</span>
          </div>
          <div class="predict-rows">
            <div
              v-for="(rec, i) in result.recommendations"
              :key="i"
              class="predict-row"
              :class="{ 'pulse-row': result.strategy === 'pulse', 'has-note': rec.constraint_summary }"
            >
              <template v-if="result.strategy === 'pulse'">
                <div class="pulse-top">
                  <span class="predict-row-label">方案 {{ i + 1 }}</span>
                  <NumberBalls :numbers="rec" :type="result.lottery_type" />
                  <span class="pulse-score" :title="'综合 ' + formatScore(rec.score)">{{ formatScore(rec.score) }}</span>
                </div>
                <p class="pulse-rationale">{{ rec.rationale }}</p>
                <div class="pulse-chips">
                  <span
                    v-for="item in rec.breakdown || []"
                    :key="item.module"
                    class="pulse-chip"
                    :class="chipClass(item.score)"
                    :title="item.note || '暂无对照'"
                  >{{ item.label }} {{ formatScore(item.score) }}</span>
                </div>
                <details class="pulse-detail">
                  <summary>分项说明</summary>
                  <p v-for="item in rec.breakdown || []" :key="item.module + '-note'">
                    <strong>{{ item.label }}</strong>
                    {{ item.note || '暂无对照' }}
                  </p>
                </details>
              </template>
              <template v-else>
                <div class="predict-row-main">
                  <span class="predict-row-label">方案 {{ i + 1 }}</span>
                  <NumberBalls :numbers="rec" :type="result.lottery_type" />
                </div>
                <p v-if="rec.constraint_summary" class="constraint-summary">{{ rec.constraint_summary }}</p>
              </template>
            </div>
          </div>
          <p class="text-xs text-muted mt-2">娱乐推荐 · 请勿当真</p>
        </div>
        <div v-if="result" class="alert alert-warn mb-4">
          <AppIcon name="alert" :size="14" style="margin-top:2px;flex:none" />
          <div>{{ result.disclaimer }}</div>
        </div>
        <div v-else class="placeholder-card mb-4">
          <div class="ph-icon"><AppIcon name="sparkle" :size="24" /></div>
          <div class="ph-title">还没有推荐方案</div>
          <div class="ph-desc">选择彩种与策略，点击「生成推荐」获取娱乐号码</div>
        </div>
      </div>

      <aside class="card predict-recent">
        <div class="card-title">
          {{ TYPE_NAMES[lotteryType] }} · 最近开奖
          <span class="sub">{{ recentHint }}</span>
        </div>
        <div v-if="recentLoading" class="loading-line"><AppIcon name="sync" :size="15" class="spin" />加载开奖…</div>
        <div v-else-if="!recent.length" class="empty" style="padding:24px 8px">
          <div class="icon"><AppIcon name="inbox" :size="22" /></div>
          <div class="empty-desc">暂无开奖数据，请先爬取</div>
        </div>
        <div v-else class="recent-list">
          <div v-for="d in recent" :key="d.id || d.issue" class="recent-item">
            <div class="recent-meta">
              <span class="recent-issue">第 {{ d.issue }} 期</span>
              <span class="recent-date">{{ d.draw_date || '—' }}</span>
            </div>
            <NumberBalls :numbers="d.numbers" :type="lotteryType" size="sm" />
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api, TYPE_NAMES } from '../api'
import NumberBalls from '../components/NumberBalls.vue'
import AppIcon from '../components/AppIcon.vue'
import { toast } from '../composables/feedback'

const LOTTERY_META = {
  ssq: { digit: false, need: 6, special: true, mainLo: 1, mainHi: 33, specLo: 1, specHi: 16, width: 2 },
  dlt: { digit: false, need: 5, special: true, mainLo: 1, mainHi: 35, specLo: 1, specHi: 12, width: 2 },
  fc3d: { digit: true, need: 3, special: false, mainLo: 0, mainHi: 9, width: 1 },
  pl3: { digit: true, need: 3, special: false, mainLo: 0, mainHi: 9, width: 1 },
  pl5: { digit: true, need: 5, special: false, mainLo: 0, mainHi: 9, width: 1 },
  qxc: { digit: true, need: 6, special: true, mainLo: 0, mainHi: 9, specLo: 0, specHi: 14, width: 1 },
  qlc: { digit: false, need: 7, special: false, mainLo: 1, mainHi: 30, width: 2 },
  kl8: { digit: false, need: 20, special: false, mainLo: 1, mainHi: 80, width: 2 },
}

function blankConstraints() {
  return {
    include_main: [],
    exclude_main: [],
    include_special: [],
    exclude_special: [],
    odd_min: '',
    odd_max: '',
    sum_min: '',
    sum_max: '',
    span_min: '',
    span_max: '',
    max_consecutive: '',
    big_min: '',
    big_max: '',
    zone1: '',
    zone2: '',
    zone3: '',
  }
}

const lotteryType = ref('ssq')
const strategy = ref('hot')
const count = ref(3)
const loading = ref(false)
const mailing = ref(false)
const mailMsg = ref('')
const result = ref(null)
const recent = ref([])
const recentLoading = ref(false)
const constraints = ref(blankConstraints())
const drafts = ref({ includeMain: '', excludeMain: '', includeSpecial: '', excludeSpecial: '' })
const storageReady = ref(false)

const STRATEGY_NAMES = {
  hot: '热号加权',
  cold: '冷号加权',
  hybrid: '冷热混合',
  random: '纯随机',
  pulse: '脉动综合',
}

const strategyHint = computed(() => ({
  hot: '更偏向近期出现次数多的号码',
  cold: '更偏向近期出现少的号码',
  hybrid: '在热号基础上略保留冷号机会',
  random: '均匀随机，与历史无关',
  pulse: '用重号、动量、邻号、跨度、连号簇、012路、和值、奇偶、质合、区位、尾数、AC值、和尾、大小、升平降、振幅、均值、中位数对照近期形态，分数不是中奖预测',
}[strategy.value]))

function strategyName(value) {
  return STRATEGY_NAMES[value] || value
}

function formatScore(score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return '—'
  return Number(score).toFixed(2)
}

function chipClass(score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return ''
  if (score >= 0.66) return 'high'
  if (score >= 0.4) return 'mid'
  return 'low'
}

const lotteryMeta = computed(() => LOTTERY_META[lotteryType.value] || LOTTERY_META.ssq)

const numberPlaceholder = computed(() => (
  lotteryMeta.value.digit ? '如 7，回车加入' : '如 03 07，回车加入'
))

const oddBalance = computed(() => {
  const need = lotteryMeta.value.need
  return { min: Math.floor(need / 2), max: Math.ceil(need / 2) }
})

const oddBalanced = computed(() => (
  String(constraints.value.odd_min) === String(oddBalance.value.min)
  && String(constraints.value.odd_max) === String(oddBalance.value.max)
))

const bigHint = computed(() => (
  lotteryMeta.value.digit ? '0–4 为小，5–9 为大' : '小于等于号码池中点为小，大于中点为大'
))

const zoneHint = computed(() => (
  lotteryMeta.value.digit ? '低区 0–3、中区 4–6、高区 7–9，三个都填才生效' : '按号码区间均分三区，三个都填才生效'
))

function storageKey(type) {
  return `yysg.predict.constraints.${type}`
}

function loadConstraints(type) {
  try {
    const raw = localStorage.getItem(storageKey(type))
    if (!raw) return blankConstraints()
    const parsed = JSON.parse(raw)
    const next = blankConstraints()
    for (const key of Object.keys(next)) {
      if (parsed[key] !== undefined && parsed[key] !== null) next[key] = parsed[key]
    }
    for (const key of ['include_main', 'exclude_main', 'include_special', 'exclude_special']) {
      if (!Array.isArray(next[key])) next[key] = []
    }
    return next
  } catch {
    return blankConstraints()
  }
}

function saveConstraints() {
  if (!storageReady.value) return
  localStorage.setItem(storageKey(lotteryType.value), JSON.stringify(constraints.value))
}

function formatBall(raw, kind) {
  const meta = lotteryMeta.value
  const special = kind.includes('special')
  const lo = special ? meta.specLo : meta.mainLo
  const hi = special ? meta.specHi : meta.mainHi
  const width = meta.width
  const text = String(raw).trim()
  if (!/^\d+$/.test(text)) return null
  const number = Number(text)
  if (number < lo || number > hi) return null
  return width > 1 ? String(number).padStart(width, '0') : String(number)
}

function addNumbers(field, draftKey) {
  const tokens = String(drafts.value[draftKey] || '').replace(/，/g, ' ').replace(/,/g, ' ').split(/\s+/).filter(Boolean)
  if (!tokens.length) return
  const next = [...constraints.value[field]]
  const invalid = []
  for (const token of tokens) {
    const ball = formatBall(token, field)
    if (!ball) {
      invalid.push(token)
      continue
    }
    if (!next.includes(ball)) next.push(ball)
    const opposite = field.startsWith('include') ? field.replace('include', 'exclude') : field.replace('exclude', 'include')
    constraints.value[opposite] = constraints.value[opposite].filter((item) => item !== ball)
  }
  constraints.value[field] = next
  drafts.value[draftKey] = ''
  if (invalid.length) toast(`号码超出范围：${invalid.join('、')}`, 'error', 3200)
}

function removeNumber(field, num) {
  constraints.value[field] = constraints.value[field].filter((item) => item !== num)
}

function toggleOddBalance() {
  if (oddBalanced.value) {
    constraints.value.odd_min = ''
    constraints.value.odd_max = ''
    return
  }
  constraints.value.odd_min = oddBalance.value.min
  constraints.value.odd_max = oddBalance.value.max
}

function toggleConsecutive() {
  constraints.value.max_consecutive = String(constraints.value.max_consecutive) === '2' ? '' : 2
}

function clearConstraints() {
  constraints.value = blankConstraints()
  drafts.value = { includeMain: '', excludeMain: '', includeSpecial: '', excludeSpecial: '' }
}

function numericOrNull(value) {
  if (value === '' || value === null || value === undefined) return null
  const number = Number(value)
  if (!Number.isInteger(number)) return null
  return number
}

function buildConstraints() {
  const src = constraints.value
  const payload = {}
  if (src.include_main.length) payload.include_main = src.include_main
  if (src.exclude_main.length) payload.exclude_main = src.exclude_main
  if (lotteryMeta.value.special && src.include_special.length) payload.include_special = src.include_special
  if (lotteryMeta.value.special && src.exclude_special.length) payload.exclude_special = src.exclude_special
  for (const key of ['odd_min', 'odd_max', 'sum_min', 'sum_max', 'span_min', 'span_max', 'big_min', 'big_max']) {
    const number = numericOrNull(src[key])
    if (number !== null) payload[key] = number
  }
  if (!lotteryMeta.value.digit) {
    const run = numericOrNull(src.max_consecutive)
    if (run !== null) payload.max_consecutive = run
  }
  const zones = [numericOrNull(src.zone1), numericOrNull(src.zone2), numericOrNull(src.zone3)]
  if (zones.some((item) => item !== null) && zones.some((item) => item === null)) {
    throw new Error('三区个数请填齐三个数')
  }
  if (zones.every((item) => item !== null)) payload.zone_counts = zones
  return payload
}

const recentHint = computed(() => {
  if (recentLoading.value) return '加载中…'
  if (!recent.value.length) return '无数据'
  return `近 ${recent.value.length} 期`
})

async function loadRecent() {
  recentLoading.value = true
  try {
    const data = await api.draws(lotteryType.value, 30)
    recent.value = data.items || []
  } catch (e) {
    recent.value = []
    console.error(e)
  } finally {
    recentLoading.value = false
  }
}

async function run() {
  loading.value = true
  mailMsg.value = ''
  try {
    const body = {
      lottery_type: lotteryType.value,
      strategy: strategy.value,
      count: count.value,
    }
    if (strategy.value !== 'pulse') {
      const filters = buildConstraints()
      if (Object.keys(filters).length) body.constraints = filters
    }
    result.value = await api.predict(body)
  } catch (e) {
    toast(e.message, 'error', 4000)
  } finally {
    loading.value = false
  }
}

async function sendMail() {
  if (!result.value) return
  mailing.value = true
  mailMsg.value = ''
  try {
    const res = await api.mailPredict({
      lottery_type: result.value.lottery_type,
      strategy: result.value.strategy,
      recommendations: result.value.recommendations,
    })
    mailMsg.value = res.ok ? (res.message || '已发送') : (res.error || '发送失败')
  } catch (e) {
    mailMsg.value = e.message
  } finally {
    mailing.value = false
  }
}

watch(lotteryType, () => {
  result.value = null
  mailMsg.value = ''
  storageReady.value = false
  constraints.value = loadConstraints(lotteryType.value)
  drafts.value = { includeMain: '', excludeMain: '', includeSpecial: '', excludeSpecial: '' }
  storageReady.value = true
  loadRecent()
})

watch(constraints, saveConstraints, { deep: true })

watch(strategy, () => {
  result.value = null
  mailMsg.value = ''
})

onMounted(() => {
  constraints.value = loadConstraints(lotteryType.value)
  storageReady.value = true
  loadRecent()
})
</script>
