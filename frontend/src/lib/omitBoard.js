import { basketProfile, normalizeNumbers } from './basket.js'
import { emptyTrendDraft, toggleTrendNumber } from './trendPick.js'

export const PREDICT_CONSTRAINT_PREFIX = 'yysg.predict.constraints.'

const TICKET = {
  ssq: { main: 6, special: 1, danMain: 6, danSpecial: 1 },
  dlt: { main: 5, special: 2, danMain: 5, danSpecial: 2 },
  qlc: { main: 7, special: 0, danMain: 7, danSpecial: 0 },
  kl8: { main: 10, special: 0, danMain: 20, danSpecial: 0 },
  fc3d: { main: 3, special: 0, danMain: 3, danSpecial: 0 },
  pl3: { main: 3, special: 0, danMain: 3, danSpecial: 0 },
  pl5: { main: 5, special: 0, danMain: 5, danSpecial: 0 },
  qxc: { main: 6, special: 1, danMain: 6, danSpecial: 1 },
}

export function constraintStorageKey(lotteryType) {
  return `${PREDICT_CONSTRAINT_PREFIX}${lotteryType}`
}

export function heatTone(stat) {
  if (!stat) return 'warm'
  if (stat.current === 0 && Number(stat.count) > 0) return 'hot'
  if (stat.cold || Number(stat.ratio) >= 1.5) return 'cold'
  if (Number(stat.ratio) >= 1) return 'cool'
  return 'warm'
}

export function emptyMarks() {
  return {
    danMain: [],
    killMain: [],
    danSpecial: [],
    killSpecial: [],
    pick: emptyTrendDraft(),
  }
}

export function blankPredictConstraints() {
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

function cloneMarks(marks) {
  return {
    danMain: [...(marks?.danMain || [])],
    killMain: [...(marks?.killMain || [])],
    danSpecial: [...(marks?.danSpecial || [])],
    killSpecial: [...(marks?.killSpecial || [])],
    pick: {
      main: [...(marks?.pick?.main || [])].map(String),
      special: [...(marks?.pick?.special || [])].map(String),
    },
  }
}

function formatBall(profile, zone, raw) {
  const special = zone === 'special'
  const lo = special ? profile.specLo : profile.mainLo
  const hi = special ? profile.specHi : profile.mainHi
  const text = String(raw ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const number = Number(text)
  if (!Number.isInteger(number) || number < lo || number > hi) return null
  return profile.width > 1 ? String(number).padStart(profile.width, '0') : String(number)
}

function sortBalls(profile, list) {
  if (profile.mode !== 'set') return list
  return [...list].sort((a, b) => Number(a) - Number(b))
}

export function toggleMark(lotteryType, marks, zone, raw, mode) {
  const next = cloneMarks(marks)
  const profile = basketProfile(lotteryType)
  const rule = TICKET[lotteryType]
  if (!profile || !rule) return { marks: next, status: 'invalid', message: '未知彩种' }
  const target = zone === 'special' ? 'special' : 'main'
  if (mode === 'pick') {
    const picked = toggleTrendNumber(lotteryType, next.pick, target, raw)
    next.pick = picked.draft
    return { marks: next, status: picked.status, message: picked.message || '' }
  }
  if (mode !== 'dan' && mode !== 'kill') {
    return { marks: next, status: 'invalid', message: '未知点选模式' }
  }
  if (target === 'special' && !rule.special) {
    return { marks: next, status: 'invalid', message: '该彩种机选没有特别号' }
  }
  const ball = formatBall(profile, target, raw)
  if (!ball) return { marks: next, status: 'invalid', message: '号码超出范围' }
  const danKey = target === 'special' ? 'danSpecial' : 'danMain'
  const killKey = target === 'special' ? 'killSpecial' : 'killMain'
  const activeKey = mode === 'kill' ? killKey : danKey
  const otherKey = mode === 'kill' ? danKey : killKey
  if (next[activeKey].includes(ball)) {
    next[activeKey] = next[activeKey].filter((item) => item !== ball)
    return { marks: next, status: 'removed', message: '' }
  }
  const cap = target === 'special' ? rule.danSpecial : rule.danMain
  if (mode === 'dan' && next[activeKey].length >= cap) {
    return { marks: cloneMarks(marks), status: 'full', message: '胆码已满' }
  }
  next[activeKey] = sortBalls(profile, [...next[activeKey], ball])
  next[otherKey] = next[otherKey].filter((item) => item !== ball)
  return { marks: next, status: 'added', message: '' }
}

export function markOf(marks, zone, raw) {
  const ball = String(raw)
  const special = zone === 'special'
  const dan = special ? marks?.danSpecial : marks?.danMain
  const kill = special ? marks?.killSpecial : marks?.killMain
  const pick = special ? marks?.pick?.special : marks?.pick?.main
  if ((dan || []).includes(ball)) return 'dan'
  if ((kill || []).includes(ball)) return 'kill'
  if ((pick || []).map(String).includes(ball)) return 'pick'
  return ''
}

export function hasConstraintMarks(marks) {
  return Boolean(
    marks?.danMain?.length
    || marks?.killMain?.length
    || marks?.danSpecial?.length
    || marks?.killSpecial?.length,
  )
}

export function mergePredictConstraints(existing, marks, lotteryType) {
  const next = blankPredictConstraints()
  const source = existing && typeof existing === 'object' ? existing : {}
  for (const key of Object.keys(next)) {
    if (source[key] !== undefined && source[key] !== null) next[key] = source[key]
  }
  const danMain = [...(marks?.danMain || [])]
  const danMainSet = new Set(danMain)
  next.include_main = danMain
  next.exclude_main = (marks?.killMain || []).filter((item) => !danMainSet.has(item))
  const profile = basketProfile(lotteryType)
  if (profile?.specCount) {
    const danSpecial = [...(marks?.danSpecial || [])]
    const danSpecialSet = new Set(danSpecial)
    next.include_special = danSpecial
    next.exclude_special = (marks?.killSpecial || []).filter((item) => !danSpecialSet.has(item))
  } else {
    next.include_special = []
    next.exclude_special = []
  }
  return next
}

export function writePredictConstraints(storage, lotteryType, marks, existing = null) {
  const next = mergePredictConstraints(existing, marks, lotteryType)
  storage.setItem(constraintStorageKey(lotteryType), JSON.stringify(next))
  return next
}

function rankCold(rows) {
  return [...(rows || [])].filter((row) => row && row.cold).sort((a, b) => {
    if (Number(b.ratio) !== Number(a.ratio)) return Number(b.ratio) - Number(a.ratio)
    if (Number(b.current) !== Number(a.current)) return Number(b.current) - Number(a.current)
    return Number(a.n) - Number(b.n)
  })
}

export function ticketPlan(lotteryType) {
  return TICKET[lotteryType] || null
}

export function coldTicket(lotteryType, board) {
  const rule = TICKET[lotteryType]
  const profile = basketProfile(lotteryType)
  if (!rule || !profile) return { ok: false, message: '未知彩种', numbers: null }
  const mainCold = rankCold(board?.main)
  if (mainCold.length < rule.main) {
    return { ok: false, message: `偏冷主号不足 ${rule.main} 个`, numbers: null }
  }
  let main = mainCold.slice(0, rule.main).map((row) => row.n)
  let special = []
  if (rule.special) {
    const specialCold = rankCold(board?.special)
    if (specialCold.length < rule.special) {
      return { ok: false, message: `偏冷特别号不足 ${rule.special} 个`, numbers: null }
    }
    special = specialCold.slice(0, rule.special).map((row) => row.n)
  }
  if (profile.mode === 'set') {
    main = sortBalls(profile, main)
    special = sortBalls(profile, special)
  }
  const parsed = normalizeNumbers(lotteryType, { main, special })
  if (!parsed.ok) return { ok: false, message: parsed.message, numbers: null }
  return { ok: true, message: '', numbers: parsed.numbers }
}

function formatCold(rows) {
  if (!rows.length) return '无'
  return rows.map((row) => `${row.n}(当前${row.current}/均${row.avg}/比${row.ratio})`).join('、')
}

export function omitSummary(board, lotteryName) {
  const lines = [
    `${lotteryName || '彩票'}遗漏看板 · 样本 ${board?.sample_size ?? 0} 期`,
    `偏冷主号：${formatCold(rankCold(board?.main).slice(0, 8))}`,
  ]
  if ((board?.special || []).length) {
    lines.push(`偏冷特别号：${formatCold(rankCold(board.special).slice(0, 8))}`)
  }
  lines.push('仅供娱乐，不构成投注建议。')
  return lines.join('\n')
}
