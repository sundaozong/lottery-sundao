import { basketProfile } from './basket.js'
import { normalizeConstraints } from './constraintPresets.js'
import { constraintStorageKey } from './omitBoard.js'

export const BASKET_COVERAGE_DISCLAIMER = '覆盖度只帮你整理号码，不构成投注建议。'

export const COVERAGE_HOT_RULE = '过热：同一区里出现不少于 2 次，且高于该区平均次数（未覆盖按 0 计入平均）。'

export const CONSTRAINTS_UPDATED_EVENT = 'yysg:constraints'

const SUMMARY_HOT_LIMIT = 8

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

function poolNumbers(profile, zone) {
  const special = zone === 'special'
  const lo = special ? profile.specLo : profile.mainLo
  const hi = special ? profile.specHi : profile.mainHi
  const numbers = []
  for (let n = lo; n <= hi; n += 1) {
    numbers.push(profile.width > 1 ? String(n).padStart(profile.width, '0') : String(n))
  }
  return numbers
}

function ticketsOf(items, lotteryType) {
  return (items || []).filter((item) => item && item.lottery_type === lotteryType)
}

function countBalls(profile, values, zone) {
  const counts = new Map()
  const list = values || []
  if (profile.mode === 'digit') {
    for (const raw of list) {
      const ball = formatBall(profile, zone, raw)
      if (!ball) continue
      counts.set(ball, (counts.get(ball) || 0) + 1)
    }
    return counts
  }
  const seen = new Set()
  for (const raw of list) {
    const ball = formatBall(profile, zone, raw)
    if (!ball || seen.has(ball)) continue
    seen.add(ball)
    counts.set(ball, (counts.get(ball) || 0) + 1)
  }
  return counts
}

function mergeCounts(target, extra) {
  for (const [ball, count] of extra) target.set(ball, (target.get(ball) || 0) + count)
}

function heatOf(count, maxCount) {
  if (!count) return 0
  if (!maxCount || maxCount <= 1) return 1
  if (count >= maxCount) return 5
  const ratio = count / maxCount
  if (ratio >= 0.75) return 4
  if (ratio >= 0.5) return 3
  if (ratio >= 0.25) return 2
  return 1
}

function buildZone(profile, zone, counts) {
  const numbers = poolNumbers(profile, zone)
  const totalHits = numbers.reduce((sum, n) => sum + (counts.get(n) || 0), 0)
  const maxCount = numbers.reduce((max, n) => Math.max(max, counts.get(n) || 0), 0)
  const poolSize = numbers.length
  const mean = poolSize ? totalHits / poolSize : 0
  const cells = numbers.map((n) => {
    const count = counts.get(n) || 0
    const hot = count >= 2 && poolSize > 0 && count * poolSize > totalHits
    return {
      n,
      count,
      uncovered: count === 0,
      hot,
      strength: maxCount ? count / maxCount : 0,
      heat: heatOf(count, maxCount),
    }
  })
  return {
    key: zone,
    label: zone === 'special' ? (profile.specialLabel || '特别号') : '主号',
    poolSize,
    covered: cells.filter((row) => row.count > 0).length,
    maxCount,
    totalHits,
    mean,
    cells,
    uncovered: cells.filter((row) => row.uncovered).map((row) => row.n),
    hot: cells.filter((row) => row.hot).map((row) => row.n),
  }
}

function formatHotList(nums) {
  if (nums.length <= SUMMARY_HOT_LIMIT) return nums.join('、')
  return `${nums.slice(0, SUMMARY_HOT_LIMIT).join('、')} 等 ${nums.length} 个`
}

function zonePhrase(zone) {
  const hot = zone.hot.length ? `过热 ${formatHotList(zone.hot)}` : '没有过热'
  return `${zone.label}已覆盖 ${zone.covered}/${zone.poolSize}，未覆盖 ${zone.uncovered.length} 个，${hot}`
}

function emptyReport(lotteryType, summary, ok = false) {
  return {
    ok,
    lotteryType: lotteryType || '',
    mode: '',
    name: '',
    ticketCount: 0,
    main: null,
    special: null,
    summary,
    rule: COVERAGE_HOT_RULE,
    disclaimer: BASKET_COVERAGE_DISCLAIMER,
  }
}

export function basketCoverage(lotteryType, items) {
  const profile = basketProfile(lotteryType)
  if (!profile) return emptyReport(lotteryType, '未知彩种')
  const tickets = ticketsOf(items, lotteryType)
  const mainCounts = new Map()
  const specialCounts = new Map()
  for (const ticket of tickets) {
    mergeCounts(mainCounts, countBalls(profile, ticket.numbers?.main, 'main'))
    if (profile.specCount) mergeCounts(specialCounts, countBalls(profile, ticket.numbers?.special, 'special'))
  }
  const main = buildZone(profile, 'main', mainCounts)
  const special = profile.specCount ? buildZone(profile, 'special', specialCounts) : null
  const summary = tickets.length
    ? [main, special].filter(Boolean).map(zonePhrase).join('；')
    : '当前彩种还没有注。'
  return {
    ok: true,
    lotteryType,
    mode: profile.mode,
    name: profile.name,
    ticketCount: tickets.length,
    main,
    special,
    summary,
    rule: COVERAGE_HOT_RULE,
    disclaimer: BASKET_COVERAGE_DISCLAIMER,
  }
}

export function formatUncoveredText(report) {
  if (!report?.ok || !report.ticketCount) return ''
  const lines = [`${report.name || report.lotteryType}未覆盖`]
  for (const zone of [report.main, report.special]) {
    if (!zone) continue
    lines.push(zone.uncovered.length ? `${zone.label} ${zone.uncovered.join(' ')}` : `${zone.label}已铺满`)
  }
  lines.push(BASKET_COVERAGE_DISCLAIMER)
  return lines.join('\n')
}

function ticketHas(profile, numbers, zone, ball) {
  const values = zone === 'special' ? numbers?.special : numbers?.main
  if (profile.mode === 'digit') {
    return (values || []).some((raw) => formatBall(profile, zone, raw) === ball)
  }
  const seen = new Set()
  for (const raw of values || []) {
    const formatted = formatBall(profile, zone, raw)
    if (formatted) seen.add(formatted)
  }
  return seen.has(ball)
}

export function coverageTicketIds(lotteryType, items, zone, raw) {
  const profile = basketProfile(lotteryType)
  if (!profile) return []
  const target = zone === 'special' ? 'special' : 'main'
  if (target === 'special' && !profile.specCount) return []
  const ball = formatBall(profile, target, raw)
  if (!ball) return []
  return ticketsOf(items, lotteryType)
    .filter((item) => ticketHas(profile, item.numbers, target, ball))
    .map((item) => item.id)
}

export function hotTicketIds(lotteryType, items, report) {
  if (!report?.ok || !report.ticketCount) return []
  const ids = []
  const seen = new Set()
  for (const zone of [report.main, report.special]) {
    if (!zone) continue
    for (const n of zone.hot) {
      for (const id of coverageTicketIds(lotteryType, items, zone.key, n)) {
        if (seen.has(id)) continue
        seen.add(id)
        ids.push(id)
      }
    }
  }
  return ids
}

function readConstraints(storage, lotteryType) {
  try {
    const raw = storage.getItem(constraintStorageKey(lotteryType))
    if (!raw) return normalizeConstraints(null)
    return normalizeConstraints(JSON.parse(raw))
  } catch {
    return normalizeConstraints(null)
  }
}

function cleanList(profile, zone, list) {
  const seen = new Set()
  const out = []
  for (const raw of list || []) {
    const ball = formatBall(profile, zone, raw)
    if (!ball || seen.has(ball)) continue
    seen.add(ball)
    out.push(ball)
  }
  out.sort((a, b) => Number(a) - Number(b))
  return out
}

function killResult(status, message, extra = {}) {
  return {
    ok: status === 'written' || status === 'unchanged' || status === 'skipped',
    status,
    message,
    addedMain: [],
    addedSpecial: [],
    skippedMain: [],
    skippedSpecial: [],
    constraints: null,
    ...extra,
  }
}

export function writeUncoveredKills(storage, lotteryType, report) {
  const profile = basketProfile(lotteryType)
  if (!profile || !report?.ok || report.lotteryType !== lotteryType) {
    return killResult('invalid', '未知彩种')
  }
  if (!report.ticketCount) return killResult('empty', '当前彩种还没有注')
  const mainUncovered = report.main?.uncovered || []
  const specialUncovered = report.special?.uncovered || []
  if (!mainUncovered.length && !specialUncovered.length) {
    return killResult('full', '号码池已经铺满，没有可写入的杀号')
  }
  const existing = readConstraints(storage, lotteryType)
  const danMain = new Set(cleanList(profile, 'main', existing.include_main))
  const danSpecial = new Set(cleanList(profile, 'special', existing.include_special))
  const excludeMain = new Set(cleanList(profile, 'main', existing.exclude_main))
  const excludeSpecial = new Set(cleanList(profile, 'special', existing.exclude_special))
  const skippedMain = mainUncovered.filter((n) => danMain.has(n))
  const skippedSpecial = specialUncovered.filter((n) => danSpecial.has(n))
  const addedMain = mainUncovered.filter((n) => !danMain.has(n) && !excludeMain.has(n))
  const addedSpecial = profile.specCount
    ? specialUncovered.filter((n) => !danSpecial.has(n) && !excludeSpecial.has(n))
    : []
  const base = {
    addedMain,
    addedSpecial,
    skippedMain,
    skippedSpecial,
  }
  if (!addedMain.length && !addedSpecial.length && !skippedMain.length && !skippedSpecial.length) {
    return killResult('unchanged', '这些未覆盖号已经在杀号里', base)
  }
  if (!addedMain.length && !addedSpecial.length) {
    return killResult('skipped', '未覆盖的号都是胆码，没有改杀号', base)
  }
  const next = {
    ...existing,
    exclude_main: cleanList(profile, 'main', [...existing.exclude_main, ...addedMain]),
    exclude_special: profile.specCount
      ? cleanList(profile, 'special', [...existing.exclude_special, ...addedSpecial])
      : existing.exclude_special,
  }
  storage.setItem(constraintStorageKey(lotteryType), JSON.stringify(next))
  const parts = []
  if (addedMain.length) parts.push(`主号 ${addedMain.length} 个`)
  if (addedSpecial.length) parts.push(`${report.special?.label || '特别号'} ${addedSpecial.length} 个`)
  let message = `已把未覆盖写入杀号：${parts.join('，')}`
  if (skippedMain.length || skippedSpecial.length) message += '。胆码未改'
  return killResult('written', message, { ...base, constraints: next })
}
