export const REPLAY_WINDOWS = [
  { id: '30', label: '30期' },
  { id: '100', label: '100期' },
  { id: '300', label: '300期' },
  { id: 'all', label: '全部' },
]

export function formatReturnRate(rate, reference) {
  if (rate === null || rate === undefined || Number.isNaN(Number(rate))) return '—'
  const text = `${(Number(rate) * 100).toFixed(1)}%`
  return reference ? `${text} 参考` : text
}

export function formatPrize(amount, reference) {
  const text = `¥ ${amount}`
  return reference ? `${text} 参考` : text
}

export function strategyReplayBlocked(strategy) {
  return strategy === 'pulse'
}

export function ticketPayload({ lotteryType, numbers, play, pick, window, multiple }) {
  const main = [...(numbers?.main || [])]
  const special = [...(numbers?.special || [])]
  const body = {
    lottery_type: lotteryType,
    bet_numbers: { main, special },
    window: window || '30',
  }
  const chosenPlay = play || numbers?.play || ''
  const chosenPick = pick ?? numbers?.pick
  if (chosenPlay) body.play = chosenPlay
  if (chosenPick) body.pick = chosenPick
  if (lotteryType === 'kl8' && !body.pick) {
    body.pick = main.length <= 10 ? main.length : 10
    body.play = 'pick'
  }
  if (multiple && Number(multiple) > 1) body.multiple = Number(multiple)
  return body
}

export function strategyPayload({ lotteryType, strategy, constraints, tickets, window }) {
  const body = {
    lottery_type: lotteryType,
    strategy: strategy || 'hot',
    tickets: tickets || 1,
    window: window || '30',
  }
  if (constraints && Object.keys(constraints).length) body.constraints = constraints
  return body
}
