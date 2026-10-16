<template>
  <div>
    <div class="page-header">
      <div>
        <h1>分析中心</h1>
        <p>开奖结果 · 冷热频次 · 遗漏 · 热力</p>
      </div>
    </div>

    <div class="chip-row">
      <button
        v-for="(name, key) in TYPE_NAMES"
        :key="key"
        type="button"
        class="chip"
        :class="{ active: type === key }"
        @click="type = key; load()"
      >{{ name }}</button>
    </div>

    <div class="alert alert-info" v-if="data">
      <span>·</span>
      <div>
        样本 {{ data.sample_size }} 期 · 数据状态
        <strong>{{ data.data_status === 'seed' ? '示例/种子' : '混合/爬取' }}</strong>
        · {{ data.disclaimer }}
      </div>
    </div>

    <div class="card mb-4">
      <div class="card-title">
        开奖结果
        <span class="sub">{{ TYPE_NAMES[type] }} · 最近 {{ draws.length }} 期</span>
      </div>
      <div v-if="drawsLoading" class="loading-line">加载开奖…</div>
      <p v-else-if="!draws.length" class="text-sm text-muted">暂无开奖数据</p>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>期号</th>
              <th>开奖日期</th>
              <th>开奖号码</th>
              <th>来源</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in draws" :key="d.id || d.issue">
              <td class="mono">{{ d.issue }}</td>
              <td>{{ d.draw_date || '—' }}</td>
              <td><NumberBalls :numbers="d.numbers" :type="type" size="sm" /></td>
              <td>
                <span class="badge" :class="d.source === 'crawl' ? 'badge-info' : 'badge-muted'">
                  {{ d.source === 'crawl' ? '爬取' : '示例' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading" class="loading-line">分析中…</div>
    <template v-else-if="data">
      <div class="grid grid-2 mb-4">
        <div class="card">
          <div class="card-title">主号频次 <span class="sub">柱越高越热</span></div>
          <div class="bar-chart">
            <div
              v-for="f in displayFreq"
              :key="f.n"
              class="bar"
              :style="{ height: barH(f.count) + '%' }"
              :title="`${f.n}: ${f.count}`"
            >
              <span class="tip" v-if="f.count">{{ f.count }}</span>
            </div>
          </div>
          <div class="bar-labels">
            <span v-for="f in displayFreq" :key="'l'+f.n">{{ f.n }}</span>
          </div>
        </div>
        <div class="card">
          <div class="card-title">热力 <span class="sub">灰度 + 蓝灰强调</span></div>
          <div class="heatmap" :style="heatGrid">
            <div
              v-for="h in data.heatmap"
              :key="h.n"
              class="heat-cell"
              :data-v="h.level"
            >{{ h.n }}</div>
          </div>
        </div>
      </div>

      <div class="grid grid-2 mb-4">
        <div class="card">
          <div class="card-title">热号 Top</div>
          <div class="balls">
            <span v-for="h in data.hot_main" :key="h.n" class="ball" :class="ballClass(type)">{{ h.n }}</span>
          </div>
          <p class="text-xs text-muted mt-3">出现次数：{{ data.hot_main.map(h => h.count).join(', ') }}</p>
        </div>
        <div class="card">
          <div class="card-title">冷号 Top</div>
          <div class="balls">
            <span v-for="h in data.cold_main" :key="h.n" class="ball ghost">{{ h.n }}</span>
          </div>
          <p class="text-xs text-muted mt-3">出现次数：{{ data.cold_main.map(h => h.count).join(', ') }}</p>
        </div>
      </div>

      <div class="card">
        <div class="card-title">遗漏（距今期数）</div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>号码</th><th>遗漏</th><th>号码</th><th>遗漏</th><th>号码</th><th>遗漏</th></tr></thead>
            <tbody>
              <tr v-for="(row, i) in omitRows" :key="i">
                <td class="mono" v-for="(cell, j) in row" :key="j">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api, TYPE_NAMES, ballClass } from '../api'
import NumberBalls from '../components/NumberBalls.vue'

const route = useRoute()
const type = ref(route.query.type || 'ssq')
const data = ref(null)
const draws = ref([])
const loading = ref(true)
const drawsLoading = ref(true)

const displayFreq = computed(() => {
  if (!data.value) return []
  const arr = data.value.main_freq || []
  if (arr.length > 40) return arr.filter((_, i) => i % 2 === 0).slice(0, 40)
  return arr.slice(0, 33)
})

const heatGrid = computed(() => {
  const n = data.value?.heatmap?.length || 11
  const cols = n > 40 ? 10 : n > 20 ? 11 : Math.min(10, n)
  return { gridTemplateColumns: `repeat(${cols}, 1fr)` }
})

const omitRows = computed(() => {
  const list = data.value?.main_omit || []
  const rows = []
  for (let i = 0; i < list.length; i += 3) {
    const chunk = list.slice(i, i + 3)
    const cells = []
    chunk.forEach((c) => { cells.push(c.n, c.omit) })
    while (cells.length < 6) cells.push('', '')
    rows.push(cells)
  }
  return rows.slice(0, 15)
})

function barH(c) {
  const mx = Math.max(...displayFreq.value.map((f) => f.count), 1)
  return Math.max(4, Math.round((c / mx) * 100))
}

async function loadDraws() {
  drawsLoading.value = true
  try {
    const history = await api.draws(type.value, 30)
    draws.value = history.items || []
  } catch (e) {
    console.error(e)
    draws.value = []
  } finally {
    drawsLoading.value = false
  }
}

async function loadAnalysis() {
  loading.value = true
  try {
    data.value = await api.analysis(type.value)
  } catch (e) {
    console.error(e)
    data.value = null
  } finally {
    loading.value = false
  }
}

function load() {
  loadDraws()
  loadAnalysis()
}

watch(() => route.query.type, (next) => {
  if (next && next !== type.value && TYPE_NAMES[next]) {
    type.value = next
    load()
  }
})

onMounted(load)
</script>
