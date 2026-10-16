<template>
  <div>
    <div class="today-bar">
      <div class="today-bar-head">
        <span class="today-bar-title">今日开奖</span>
        <span class="today-bar-date">{{ schedule.label }}</span>
      </div>
      <div class="today-bar-chips">
        <router-link
          v-for="item in schedule.today"
          :key="item.type"
          class="chip active"
          :to="`/analysis?type=${item.type}`"
        >{{ item.name }}</router-link>
        <span v-if="!schedule.today.length" class="today-off">今日无开奖</span>
      </div>
      <p v-if="schedule.off.length" class="today-off">
        今日不开 {{ schedule.off.map((item) => item.name).join('、') }}
      </p>
    </div>

    <div class="page-header">
      <div>
        <h1>观测台</h1>
        <p>今晚的号码、账本与推荐，一眼看清</p>
      </div>
    </div>

    <div class="alert alert-disclaimer">
      <span>·</span>
      <div>个人观测站 · 开奖可能为<strong>种子/爬取</strong>数据；预测<strong>仅供娱乐</strong>，请勿据此决策。</div>
    </div>

    <div class="grid grid-4 mb-4">
      <div class="card stat">
        <div class="stat-label">累计投入</div>
        <div class="stat-value">¥ {{ summary.total_cost ?? '—' }}</div>
      </div>
      <div class="card stat">
        <div class="stat-label">累计奖金</div>
        <div class="stat-value ok">¥ {{ summary.total_prize ?? '—' }}</div>
      </div>
      <div class="card stat">
        <div class="stat-label">净盈亏</div>
        <div class="stat-value" :class="(summary.net || 0) >= 0 ? 'ok' : 'danger'">
          {{ (summary.net || 0) >= 0 ? '' : '− ' }}¥ {{ Math.abs(summary.net || 0) }}
        </div>
      </div>
      <div class="card stat">
        <div class="stat-label">关注彩种</div>
        <div class="stat-value gold">{{ draws.length || 7 }}</div>
      </div>
    </div>

    <div class="mb-4">
      <div class="quick-grid">
        <router-link class="quick-item" to="/analysis"><span class="qi">▣</span>分析走势</router-link>
        <router-link class="quick-item" to="/predict"><span class="qi">✦</span>今日推荐</router-link>
        <router-link class="quick-item" to="/records"><span class="qi">☰</span>记一笔</router-link>
        <router-link class="quick-item" to="/prize"><span class="qi">¥</span>算奖金</router-link>
      </div>
    </div>

    <div class="card mb-4">
      <div class="card-title">
        各彩种最新开奖
        <span class="sub">{{ statusHint }}</span>
      </div>
      <div v-if="loading" class="loading-line">加载中…</div>
      <div v-else class="grid grid-auto">
        <router-link
          v-for="d in draws"
          :key="d.lottery_type"
          class="card lottery-card"
          :to="`/analysis?type=${d.lottery_type}`"
        >
          <div class="lottery-name">{{ d.name }}</div>
          <div class="issue">第 {{ d.issue }} 期 · {{ d.source === 'crawl' ? '爬取' : '示例' }}</div>
          <NumberBalls :numbers="d.numbers" :type="d.lottery_type" />
          <div class="meta">
            <span>{{ d.draw_date || '—' }}</span>
            <span>去分析 →</span>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, lotteriesOn } from '../api'
import NumberBalls from '../components/NumberBalls.vue'

const schedule = lotteriesOn()
const draws = ref([])
const summary = ref({})
const loading = ref(true)

const statusHint = computed(() => {
  const sources = draws.value.map((d) => d.source)
  if (!sources.length) return '暂无数据'
  if (sources.every((s) => s === 'seed')) return '当前为种子示例数据'
  if (sources.every((s) => s === 'crawl')) return '来自爬取'
  return '种子与爬取混合'
})

onMounted(async () => {
  try {
    const [latest, records] = await Promise.all([api.latest(), api.records()])
    draws.value = latest.items || []
    summary.value = records.summary || {}
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>
