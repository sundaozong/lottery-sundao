<template>
  <div>
    <div class="page-header">
      <div>
        <h1>分析中心</h1>
        <p>开奖走势 · 冷热频次 · 遗漏 · 热力 · 回声 · 结伴</p>
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
      <AppIcon name="info" :size="14" style="margin-top:2px;flex:none" />
      <div>
        样本 {{ data.sample_size }} 期 · 数据状态
        <strong>{{ data.data_status === 'seed' ? '示例/种子' : '混合/爬取' }}</strong>
        · {{ data.disclaimer }}
      </div>
    </div>

    <div class="card mb-4">
      <div class="card-title">
        开奖结果
        <span class="sub">{{ TYPE_NAMES[type] }} · 基本走势（开出为彩球，灰字为遗漏）</span>
      </div>
      <div v-if="drawsLoading" class="loading-line"><AppIcon name="sync" :size="15" class="spin" />加载开奖…</div>
      <TrendChart
        v-else
        :type="type"
        :draws="draws"
        v-model:periods="periods"
        :period-options="[50, 80, 120, 300]"
      />
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>开奖回声</span>
        <span class="sub">{{ echoField.digit ? '按位对照' : '号码集合对照' }} · 近 80 期 · 仅供娱乐</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>回声对照仅供娱乐，不代表下期结果；请理性购彩。</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="echoMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="echoSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-primary" type="button" :disabled="echoLoading" @click="runEcho">
            <AppIcon v-if="echoLoading" name="sync" :size="14" class="spin" />
            {{ echoLoading ? '对照中…' : '对照' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="echoLoading" @click="fillLatestEcho">用最新开奖对照</button>
        </div>
        <p class="form-hint">
          {{ echoField.digit ? '同一位置数字相同才算重合，顺序不能打乱。' : '看号码重合了几个，先后顺序不影响。' }}
        </p>
        <p v-if="echoError" class="bet-error">{{ echoError }}</p>
        <div v-if="echoResult" class="echo-list">
          <p class="text-xs text-muted">
            样本 {{ echoResult.sample_size }} 期
            <template v-if="echoResult.echoes.length"> · {{ echoResult.echoes.length }} 条回声</template>
          </p>
          <div v-if="!echoResult.echoes.length" class="empty">
            <div class="empty-title">没有重合</div>
            <div class="empty-desc">这注在样本里没有和历史开奖撞上的号码</div>
          </div>
          <div v-for="row in echoResult.echoes" :key="row.issue" class="echo-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span class="mono">第 {{ row.issue }} 期</span>
                <span v-if="row.draw_date">{{ row.draw_date }}</span>
                <span v-if="row.exact_match" class="source-badge">完全重合</span>
              </div>
              <NumberBalls
                :numbers="{ main: row.main, special: row.special }"
                :type="type"
                :marks="echoMarks(row)"
                size="sm"
              />
            </div>
            <div class="echo-score">
              <div class="echo-score-num">{{ row.score }}</div>
              <div class="text-xs text-muted">主号 {{ row.main_shared }}<template v-if="showSpecialShare"> · 特别 {{ row.special_shared }}</template></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>号码结伴</span>
        <span class="sub">主号共现 · 近 {{ affinityWindow }} 期 · 仅供娱乐</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ affinity?.disclaimer || '号码结伴只看近期开奖里哪些号码一起出现，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">{{ affinityDigit ? '看某个数字' : '看某个号' }}</label>
            <input
              v-model="affinitySeed"
              class="form-input mono"
              :placeholder="affinityDigit ? '如 7' : '如 07'"
              @keydown.enter="loadAffinity"
            />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-primary" type="button" :disabled="affinityLoading" @click="loadAffinity">
            <AppIcon v-if="affinityLoading" name="sync" :size="14" class="spin" />
            {{ affinityLoading ? '统计中…' : '查看结伴' }}
          </button>
          <button
            v-if="affinitySeed.trim()"
            class="btn btn-ghost"
            type="button"
            :disabled="affinityLoading"
            @click="clearAffinitySeed"
          >看整体</button>
        </div>
        <p class="form-hint">{{ affinityHint }}</p>
        <p v-if="affinityError" class="bet-error">{{ affinityError }}</p>
        <div v-if="affinityLoading && !affinity" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计结伴…
        </div>
        <div v-else-if="affinity" class="affinity-list">
          <p class="text-xs text-muted">
            样本 {{ affinity.sample_size }} 期
            <template v-if="affinity.seed"> · 正在看 {{ affinity.seed }}</template>
            <template v-if="affinity.mode === 'digit'"> · 不同位置</template>
          </p>
          <div v-if="!affinity.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有主号样本后，这里会列出经常一起出现的号码</div>
          </div>
          <template v-else>
            <div v-if="affinity.seed" class="affinity-block">
              <div class="card-title">{{ affinityDigit ? '这个数字的结伴' : '这个号的结伴' }}
                <span class="sub">出现时对方也在</span>
              </div>
              <div v-for="group in affinity.companions" :key="affinityKey(group)" class="affinity-group">
                <div v-if="!group.appearances" class="empty">
                  <div class="empty-title">样本里没有这个号</div>
                  <div class="empty-desc">换一个号码，或看看下面经常一起出现的组合</div>
                </div>
                <template v-else>
                  <div class="affinity-side affinity-anchor">
                    <span v-if="group.position_label" class="pos-label">{{ group.position_label }}</span>
                    <NumberBalls
                      interactive
                      :numbers="{ main: [group.n] }"
                      :type="type"
                      size="sm"
                      @pick="pickAffinitySeed"
                    />
                    <span class="text-xs text-muted">出现 {{ group.appearances }} 次</span>
                  </div>
                  <div v-if="!group.companions.length" class="text-xs text-muted">没有其他号码和它一起出现</div>
                  <div v-for="item in group.companions" :key="affinityKey(item)" class="affinity-companion">
                    <div class="affinity-side">
                      <span v-if="item.position_label" class="pos-label">{{ item.position_label }}</span>
                      <NumberBalls
                        interactive
                        :numbers="{ main: [item.n] }"
                        :type="type"
                        size="sm"
                        @pick="pickAffinitySeed"
                      />
                    </div>
                    <div class="affinity-note" title="这个号出现的期里，对方也出现的比例">{{ item.count }} 次 · 同行 {{ affinityRate(item.rate) }}</div>
                  </div>
                </template>
              </div>
            </div>

            <div v-else-if="affinityGroups.length" class="affinity-block">
              <div class="card-title">热号结伴 <span class="sub">出现时对方也在 · 点号码可只看它</span></div>
              <div v-for="group in affinityGroups" :key="affinityKey(group)">
                <div class="affinity-side affinity-anchor">
                  <span v-if="group.position_label" class="pos-label">{{ group.position_label }}</span>
                  <NumberBalls
                    interactive
                    :numbers="{ main: [group.n] }"
                    :type="type"
                    size="sm"
                    @pick="pickAffinitySeed"
                  />
                  <span class="text-xs text-muted">出现 {{ group.appearances }} 次</span>
                </div>
                <div v-for="item in group.companions" :key="affinityKey(group) + '-' + affinityKey(item)" class="affinity-companion">
                  <div class="affinity-side">
                    <span v-if="item.position_label" class="pos-label">{{ item.position_label }}</span>
                    <NumberBalls
                      interactive
                      :numbers="{ main: [item.n] }"
                      :type="type"
                      size="sm"
                      @pick="pickAffinitySeed"
                    />
                  </div>
                  <div class="affinity-note" title="这个号出现的期里，对方也出现的比例">{{ item.count }} 次 · 同行 {{ affinityRate(item.rate) }}</div>
                </div>
              </div>
            </div>

            <div class="affinity-block">
              <div class="card-title">常一起出现 <span class="sub">占全部样本</span></div>
              <div v-if="!affinity.top_pairs.length" class="empty">
                <div class="empty-title">还没有成对的号码</div>
                <div class="empty-desc">样本里的主号太少，凑不成一对</div>
              </div>
              <div
                v-for="pair in affinity.top_pairs"
                :key="pairKey(pair)"
                class="affinity-pair"
              >
                <div class="affinity-side">
                  <span v-if="pair.label_a" class="pos-label">{{ pair.label_a }}</span>
                  <NumberBalls
                    interactive
                    :numbers="{ main: [pair.a] }"
                    :type="type"
                    size="sm"
                    @pick="pickAffinitySeed"
                  />
                  <span class="plus">+</span>
                  <span v-if="pair.label_b" class="pos-label">{{ pair.label_b }}</span>
                  <NumberBalls
                    interactive
                    :numbers="{ main: [pair.b] }"
                    :type="type"
                    size="sm"
                    @pick="pickAffinitySeed"
                  />
                </div>
                <div class="affinity-note" title="两号出现在同一期的次数，占样本期数">{{ pair.count }} 次 · 占 {{ affinityRate(pair.rate) }}</div>
              </div>
            </div>

            <div v-if="affinity.special && affinity.special.top_pairs.length" class="affinity-block">
              <div class="card-title">{{ affinity.special.label }} <span class="sub">和主号一起出现，不计入上面的结伴</span></div>
              <div v-for="row in affinity.special.top_pairs.slice(0, 4)" :key="specialKey(row)" class="affinity-companion">
                <div class="affinity-side">
                  <span v-if="row.position_label" class="pos-label">{{ row.position_label }}</span>
                  <NumberBalls
                    :numbers="{ main: [row.main || row.n], special: [row.special] }"
                    :type="type"
                    size="sm"
                  />
                </div>
                <div class="affinity-note">{{ row.count }} 次 · 占 {{ affinityRate(row.rate) }}</div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-line"><AppIcon name="sync" :size="15" class="spin" />分析中…</div>
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

      <div v-if="shape" class="mb-4">
        <div class="section-head">
          <span>号码形态</span>
          <span class="sub">近 {{ shape.sample_size }} 期主号 · 不含蓝球/特别号 · 仅供娱乐</span>
        </div>
        <div v-if="!shape.sample_size" class="card">
          <div class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有主号样本后，这里会统计奇偶、大小、和值与连号</div>
          </div>
        </div>
        <template v-else>
          <div class="grid grid-4 mb-4">
            <div class="card stat">
              <div class="stat-label">和值均值</div>
              <div class="stat-value">{{ shape.sum.avg }}</div>
            </div>
            <div class="card stat">
              <div class="stat-label">{{ shape.mode === 'set' ? '含连号' : '跨度均值' }}</div>
              <div class="stat-value">{{ shape.mode === 'set' ? `${shape.consecutive.draws_with}/${shape.sample_size}` : shape.span.avg }}</div>
            </div>
            <div class="card stat">
              <div class="stat-label">常见奇偶</div>
              <div class="stat-value compact">{{ shape.odd_even[0]?.label || '—' }}</div>
            </div>
            <div class="card stat">
              <div class="stat-label">常见大小</div>
              <div class="stat-value compact">{{ shape.big_small[0]?.label || '—' }}</div>
            </div>
          </div>
          <p class="text-xs text-muted mb-4">
            连号 {{ shape.consecutive.draws_with }} 期，平均 {{ shape.consecutive.avg_pairs }} 组
            · 和值 {{ shape.sum.min }}–{{ shape.sum.max }}
            · 跨度 {{ shape.span.min }}–{{ shape.span.max }}
          </p>
          <div class="grid grid-2 mb-4">
            <div class="card">
              <div class="card-title">奇偶 <span class="sub">主号个数</span></div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>比例</th><th>期数</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.odd_even.slice(0, 8)" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td class="mono">{{ row.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="card">
              <div class="card-title">和值区间</div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>区间</th><th>期数</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.sum.buckets" :key="row.label">
                      <td class="mono">{{ row.label }}</td>
                      <td class="mono">{{ row.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div v-if="shape.zones.length || shape.patterns.length" class="grid grid-2">
            <div v-if="shape.zones.length" class="card">
              <div class="card-title">区间 <span class="sub">平均个数</span></div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>区间</th><th>平均</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.zones" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td class="mono">{{ row.avg }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div v-if="shape.patterns.length" class="card">
              <div class="card-title">三位形态</div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>形态</th><th>期数</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.patterns" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td class="mono">{{ row.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </template>
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
import TrendChart from '../components/TrendChart.vue'
import AppIcon from '../components/AppIcon.vue'

const ECHO_FIELDS = {
  ssq: { main: '01 02 03 04 05 06', special: '16', specialLabel: '蓝球', digit: false },
  dlt: { main: '05 11 19 28 33', special: '02 10', specialLabel: '后区', digit: false },
  qlc: { main: '03 08 12 18 21 25 29', special: '09', specialLabel: '特别号', digit: false },
  kl8: { main: '01 05 12 18 22 27', special: '', specialLabel: '', digit: false },
  fc3d: { main: '1 2 3', special: '', specialLabel: '', digit: true },
  pl3: { main: '1 2 3', special: '', specialLabel: '', digit: true },
  pl5: { main: '1 2 3 4 5', special: '', specialLabel: '', digit: true },
  qxc: { main: '1 2 3 4 5 6', special: '7', specialLabel: '特别号', digit: true },
}

const route = useRoute()
const type = ref(route.query.type || 'ssq')
const data = ref(null)
const shape = ref(null)
const draws = ref([])
const periods = ref(50)
const loading = ref(true)
const drawsLoading = ref(true)
const echoMain = ref('')
const echoSpecial = ref('')
const echoResult = ref(null)
const echoError = ref('')
const echoLoading = ref(false)
const affinity = ref(null)
const affinitySeed = ref('')
const affinityError = ref('')
const affinityLoading = ref(false)
let affinityToken = 0

const echoField = computed(() => ECHO_FIELDS[type.value] || ECHO_FIELDS.ssq)
const affinityDigit = computed(() => echoField.value.digit)
const affinityWindow = computed(() => Math.min(Math.max(periods.value, 50), 200))
const affinityHint = computed(() => (
  affinityDigit.value
    ? '只看不同位置。点一个数字，看其他位置经常一起开出什么。'
    : '主号不分先后。点一个球，看它开出时还经常带上谁。'
))
const affinityGroups = computed(() => {
  const groups = affinity.value?.companions || []
  if (affinity.value?.seed) return groups
  return groups.slice(0, 4).map((group) => ({
    ...group,
    companions: (group.companions || []).slice(0, 3),
  }))
})
const showSpecialShare = computed(() => Boolean(echoField.value.specialLabel))

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
    const history = await api.draws(type.value, 300)
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
  const limit = Math.max(periods.value, 50)
  try {
    const [analysis, shapeRes] = await Promise.all([
      api.analysis(type.value, limit),
      api.shape(type.value, limit).catch((e) => {
        console.error(e)
        return null
      }),
    ])
    data.value = analysis
    shape.value = shapeRes
  } catch (e) {
    console.error(e)
    data.value = null
    shape.value = null
  } finally {
    loading.value = false
  }
}

function splitNums(text) {
  return String(text || '').trim().split(/[\s,，]+/).filter(Boolean)
}

function echoMarks(row) {
  const query = echoResult.value?.query
  if (!query) return null
  const specialSet = new Set(row.shared_special || [])
  if (echoResult.value.mode === 'digit') {
    return {
      main: (row.main || []).map((n, i) => (n === query.main[i] ? true : null)),
      special: (row.special || []).map((n) => (specialSet.has(n) ? true : null)),
    }
  }
  const mainSet = new Set(row.shared_main || [])
  return {
    main: (row.main || []).map((n) => (mainSet.has(n) ? true : null)),
    special: (row.special || []).map((n) => (specialSet.has(n) ? true : null)),
  }
}

async function runEcho() {
  echoLoading.value = true
  echoError.value = ''
  try {
    const main = splitNums(echoMain.value)
    const special = echoField.value.specialLabel ? splitNums(echoSpecial.value) : []
    echoResult.value = await api.echo(type.value, { main, special, limit: 80, top: 8 })
  } catch (e) {
    echoResult.value = null
    echoError.value = e.message || '对照失败'
  } finally {
    echoLoading.value = false
  }
}

async function fillLatestEcho() {
  echoError.value = ''
  try {
    const history = await api.draws(type.value, 1)
    const latest = history.items?.[0]
    if (!latest) {
      echoResult.value = null
      echoError.value = '暂无开奖可对照'
      return
    }
    echoMain.value = (latest.numbers?.main || []).join(' ')
    echoSpecial.value = (latest.numbers?.special || []).join(' ')
    await runEcho()
  } catch (e) {
    echoError.value = e.message || '读取开奖失败'
  }
}

function affinityRate(rate) {
  const value = Number(rate)
  if (!Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function affinityKey(item) {
  return `${item.position ?? ''}-${item.n}`
}

function pairKey(pair) {
  return `${pair.pos_a ?? ''}-${pair.a}-${pair.pos_b ?? ''}-${pair.b}`
}

function specialKey(row) {
  return `${row.position ?? ''}-${row.main || row.n}-${row.special}`
}

function pickAffinitySeed(n) {
  affinitySeed.value = String(n ?? '')
  loadAffinity()
}

function clearAffinitySeed() {
  affinitySeed.value = ''
  loadAffinity()
}

async function loadAffinity() {
  const token = ++affinityToken
  affinityLoading.value = true
  affinityError.value = ''
  const seed = affinitySeed.value.trim()
  try {
    const body = await api.affinity(type.value, { limit: affinityWindow.value, seed: seed || undefined })
    if (token !== affinityToken) return
    affinity.value = body
    affinitySeed.value = body.seed || ''
  } catch (e) {
    if (token !== affinityToken) return
    affinity.value = null
    affinityError.value = e.message || '结伴加载失败'
  } finally {
    if (token === affinityToken) affinityLoading.value = false
  }
}

function load() {
  shape.value = null
  echoResult.value = null
  echoError.value = ''
  echoMain.value = ''
  echoSpecial.value = ''
  affinity.value = null
  affinityError.value = ''
  affinitySeed.value = ''
  loadDraws()
  loadAnalysis()
  loadAffinity()
}

watch(periods, () => {
  loadAnalysis()
  loadAffinity()
})

watch(() => route.query.type, (next) => {
  if (next && next !== type.value && TYPE_NAMES[next]) {
    type.value = next
    load()
  }
})

onMounted(load)
</script>
