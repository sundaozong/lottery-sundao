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
              :class="{ 'pulse-row': result.strategy === 'pulse' }"
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
                <span class="predict-row-label">方案 {{ i + 1 }}</span>
                <NumberBalls :numbers="rec" :type="result.lottery_type" />
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

const lotteryType = ref('ssq')
const strategy = ref('hot')
const count = ref(3)
const loading = ref(false)
const mailing = ref(false)
const mailMsg = ref('')
const result = ref(null)
const recent = ref([])
const recentLoading = ref(false)

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
    result.value = await api.predict({
      lottery_type: lotteryType.value,
      strategy: strategy.value,
      count: count.value,
    })
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
  loadRecent()
})

watch(strategy, () => {
  result.value = null
  mailMsg.value = ''
})

onMounted(loadRecent)
</script>
