import { reactive } from 'vue'

const state = reactive({
  open: false,
  mode: 'ticket',
  lotteryType: 'ssq',
  numbers: { main: [], special: [] },
  play: '',
  pick: null,
  strategy: 'hot',
  constraints: null,
})

export function useReplay() {
  function openTicket({ lotteryType, numbers, play, pick } = {}) {
    state.mode = 'ticket'
    state.lotteryType = lotteryType || 'ssq'
    state.numbers = {
      main: [...(numbers?.main || [])],
      special: [...(numbers?.special || [])],
      play: numbers?.play,
      pick: numbers?.pick,
    }
    state.play = play || ''
    state.pick = pick ?? null
    state.strategy = 'hot'
    state.constraints = null
    state.open = true
  }

  function openStrategy({ lotteryType, strategy, constraints } = {}) {
    state.mode = 'strategy'
    state.lotteryType = lotteryType || 'ssq'
    state.strategy = strategy || 'hot'
    state.constraints = constraints && Object.keys(constraints).length ? { ...constraints } : null
    state.numbers = { main: [], special: [] }
    state.open = true
  }

  function hide() {
    state.open = false
  }

  return { state, openTicket, openStrategy, hide }
}
