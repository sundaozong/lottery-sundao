export function formatBall(raw, zone) {
  const text = String(raw ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const number = Number(text)
  if (!zone || number < zone.lo || number > zone.hi) return null
  return zone.width > 1 ? String(number).padStart(zone.width, '0') : String(number)
}

export function parseBalls(value, zone, max = 0) {
  const tokens = String(value ?? '').trim().split(/[\s,，]+/).filter(Boolean)
  const balls = []
  const invalid = []
  const seen = new Set()
  for (const token of tokens) {
    const ball = formatBall(token, zone)
    if (!ball) {
      invalid.push(token)
      continue
    }
    if (seen.has(ball)) continue
    seen.add(ball)
    balls.push(ball)
  }
  balls.sort((a, b) => Number(a) - Number(b))
  return { balls: max > 0 ? balls.slice(0, max) : balls, invalid }
}

export function ticketKey(ticket) {
  const main = (ticket?.main || []).join(',')
  const special = (ticket?.special || []).join(',')
  return `${main}|${special}`
}

export function basketDrafts(lotteryType, tickets) {
  return (tickets || []).map((ticket) => ({
    lottery_type: lotteryType,
    numbers: {
      main: [...(ticket.main || [])],
      special: [...(ticket.special || [])],
    },
    source: 'expand',
    note: '',
  }))
}
