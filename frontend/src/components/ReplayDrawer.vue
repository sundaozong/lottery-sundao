<template>
  <div v-if="state.open" class="basket-mask replay-mask" @click.self="hide">
    <aside class="basket-drawer replay-drawer" role="dialog" aria-modal="true" aria-label="历史回放">
      <header class="basket-head">
        <div>
          <div class="basket-title">历史回放</div>
          <p class="form-hint">{{ subtitle }}</p>
        </div>
        <button class="icon-btn" type="button" aria-label="关闭回放" @click="hide">
          <AppIcon name="x" />
        </button>
      </header>

      <div class="basket-scroll">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:2px;flex:none" />
          <div>彩票每期开奖是<strong>独立随机事件</strong>。回放只对照本地历史，<strong>不代表未来</strong>，也不构成投注建议。</div>
        </div>

        <div class="chip-row compact">
          <button
            v-for="item in REPLAY_WINDOWS"
            :key="item.id"
            type="button"
            class="chip"
            :class="{ active: windowId === item.id }"
            :disabled="loading"
            @click="setWindow(item.id)"
          >{{ item.label }}</button>
        </div>
        <div v-if="state.mode === 'strategy'" class="chip-row compact">
          <button
            v-for="count in ticketChoices"
            :key="count"
            type="button"
            class="chip"
            :class="{ active: tickets === count }"
            :disabled="loading"
            @click="setTickets(count)"
          >每期 {{ count }} 注</button>
        </div>

        <p v-if="loading" class="form-hint">回放中…</p>
        <p v-if="error" class="bet-error">{{ error }}</p>

        <template v-if="report && !loading">
          <p v-if="report.cap_note" class="form-hint">{{ report.cap_note }}</p>
          <p class="form-hint">对照 {{ report.sample_size }} 期<template v-if="report.history_size"> · 本地共 {{ report.history_size }} 期</template></p>

          <section v-for="block in blocks" :key="block.key" class="replay-block">
            <h3>{{ block.title }}</h3>
            <div v-if="block.numbers" class="replay-ticket">
              <NumberBalls :numbers="block.numbers" :type="state.lotteryType" size="sm" />
              <button class="btn btn-ghost btn-sm" type="button" @click="addNumbers(block.numbers)">加入选号篮</button>
            </div>
            <div class="replay-stats">
              <div class="replay-stat">
                <span>总投入</span>
                <strong>¥ {{ block.spent }}</strong>
              </div>
              <div class="replay-stat">
                <span>总奖金</span>
                <strong :class="block.prize_is_reference ? '' : 'ok'">{{ formatPrize(block.prize, block.prize_is_reference) }}</strong>
              </div>
              <div class="replay-stat">
                <span>回报率</span>
                <strong>{{ formatReturnRate(block.return_rate, block.prize_is_reference) }}</strong>
              </div>
              <div class="replay-stat">
                <span>最长不中</span>
                <strong>{{ block.longest_miss }} 期</strong>
              </div>
            </div>
            <p v-if="block.prize_is_reference" class="form-hint">含浮动奖，总奖金和回报率标为参考。</p>
            <p v-if="!block.sample_size" class="form-hint">这段没有可对照的开奖。</p>

            <div v-if="block.best" class="replay-best">
              <div class="replay-best-title">最好成绩 · {{ block.best.issue }} · {{ block.best.level }}</div>
              <div class="replay-ticket">
                <NumberBalls :numbers="block.best.numbers" :type="state.lotteryType" size="sm" />
                <span class="text-xs text-muted">{{ block.best.amount_label }}</span>
                <button class="btn btn-ghost btn-sm" type="button" @click="addNumbers(block.best.numbers)">加入选号篮</button>
              </div>
            </div>

            <div v-if="block.latest_tickets?.length" class="replay-latest">
              <div class="form-hint">最近一期开出前，会买这些号</div>
              <div v-for="(ticket, index) in block.latest_tickets" :key="index" class="replay-ticket">
                <NumberBalls :numbers="ticket" :type="state.lotteryType" size="sm" />
                <button class="btn btn-ghost btn-sm" type="button" @click="addNumbers(ticket)">加入选号篮</button>
              </div>
            </div>

            <div v-if="block.levels?.length" class="table-wrap">
              <table>
                <thead><tr><th>奖级</th><th>次数</th><th>金额</th></tr></thead>
                <tbody>
                  <tr v-for="row in block.levels" :key="block.key + row.level">
                    <td>{{ row.level }}</td>
                    <td class="mono">{{ row.count }}</td>
                    <td class="mono">{{ row.amount_label }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <p class="text-xs text-muted">{{ report.disclaimer }}</p>
          <p class="text-xs text-muted">{{ report.note }}</p>
        </template>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { api, TYPE_NAMES } from '../api'
import { toast } from '../composables/feedback'
import { useBasket } from '../composables/useBasket'
import { useReplay } from '../composables/useReplay'
import { REPLAY_WINDOWS, formatPrize, formatReturnRate, strategyPayload, ticketPayload } from '../lib/replay'
import AppIcon from './AppIcon.vue'
import NumberBalls from './NumberBalls.vue'

const { state, hide } = useReplay()
const basket = useBasket()
const windowId = ref('30')
const tickets = ref(1)
const ticketChoices = [1, 2, 3]
const loading = ref(false)
const error = ref('')
const report = ref(null)
let seq = 0

const subtitle = computed(() => {
  const name = TYPE_NAMES[state.lotteryType] || state.lotteryType
  if (state.mode === 'strategy') return `${name} · 条件逐期前推 · 对照纯随机`
  return `${name} · 这一注如果过去一直买`
})

const blocks = computed(() => {
  const data = report.value
  if (!data) return []
  if (state.mode === 'ticket') {
    return [{
      key: 'ticket',
      title: data.play_name || '这一注',
      numbers: data.bet,
      ...data,
    }]
  }
  return [
    { key: 'strategy', title: `这套条件 · ${data.strategy?.label || ''}`, ...data.strategy },
    { key: 'baseline', title: '纯随机基线', ...data.baseline },
  ]
})

async function run() {
  const current = ++seq
  loading.value = true
  error.value = ''
  try {
    const data = state.mode === 'strategy'
      ? await api.replayStrategy(strategyPayload({
        lotteryType: state.lotteryType,
        strategy: state.strategy,
        constraints: state.constraints,
        tickets: tickets.value,
        window: windowId.value,
      }))
      : await api.replayTicket(ticketPayload({
        lotteryType: state.lotteryType,
        numbers: state.numbers,
        play: state.play,
        pick: state.pick,
        window: windowId.value,
      }))
    if (current !== seq) return
    report.value = data
  } catch (err) {
    if (current !== seq) return
    report.value = null
    error.value = err.message || '回放失败'
  } finally {
    if (current === seq) loading.value = false
  }
}

function setWindow(id) {
  if (windowId.value === id || loading.value) return
  windowId.value = id
  run()
}

function setTickets(count) {
  if (tickets.value === count || loading.value) return
  tickets.value = count
  run()
}

function addNumbers(numbers) {
  if (!numbers) return
  const outcome = basket.add({
    lottery_type: state.lotteryType,
    numbers: { main: numbers.main || [], special: numbers.special || [] },
    source: 'replay',
    strategy: state.mode === 'strategy' ? state.strategy : '',
  })
  const kind = outcome.status === 'added' ? 'ok' : outcome.status === 'duplicate' ? 'info' : 'error'
  toast(outcome.message, kind)
}

watch(
  () => [
    state.open,
    state.mode,
    state.lotteryType,
    state.strategy,
    state.numbers.main.join(','),
    state.numbers.special.join(','),
    JSON.stringify(state.constraints || {}),
  ],
  () => {
    if (!state.open) return
    windowId.value = '30'
    tickets.value = 1
    report.value = null
    error.value = ''
    run()
  },
)
</script>
