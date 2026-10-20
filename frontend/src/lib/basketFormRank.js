export const BASKET_FORM_RANK_DISCLAIMER = '形态打分对照本地历史的常见带，只整理当前篮里的注，不推荐下期号码。不是脉动。仅供娱乐，不构成投注建议。'

export const FORM_RANK_LIMIT = 80

export const FORM_RANK_METRIC_MAX = 8

const SAMPLE_GLANCES = new Set(['还没有历史可对照', '这注形态算不出来'])

export function defaultMinCentered(available) {
  const count = Number(available)
  if (!Number.isFinite(count) || count <= 0) return 0
  return Math.ceil(count / 2)
}

export function parseMinCentered(raw, max = FORM_RANK_METRIC_MAX) {
  if (raw == null || (typeof raw === 'string' && raw.trim() === '')) {
    return { ok: true, value: null, message: '' }
  }
  const number = typeof raw === 'number' ? raw : Number(String(raw).trim())
  if (!Number.isInteger(number) || number < 0 || number > max) {
    return {
      ok: false,
      value: null,
      message: `最低居中项数请填 0 到 ${max} 的整数，留空则按一半。`,
    }
  }
  return { ok: true, value: number, message: '' }
}

function countStances(metrics) {
  const counts = { center: 0, low: 0, high: 0, unavailable: 0 }
  for (const item of metrics || []) {
    if (Object.prototype.hasOwnProperty.call(counts, item?.stance)) counts[item.stance] += 1
  }
  return counts
}

function specialNote(metrics) {
  if (!metrics?.length) return ''
  const counts = countStances(metrics)
  const parts = []
  if (counts.center) parts.push(`${counts.center} 居中`)
  if (counts.low) parts.push(`${counts.low} 偏低`)
  if (counts.high) parts.push(`${counts.high} 偏高`)
  if (counts.unavailable) parts.push(`${counts.unavailable} 暂无`)
  return parts.length ? `特别号 ${parts.join(' · ')}` : ''
}

function blankScore(extra) {
  return {
    ok: false,
    pending: false,
    score: null,
    low: 0,
    high: 0,
    skew: null,
    available: 0,
    unavailable: 0,
    glance: '',
    specialNote: '',
    error: '',
    sampleShort: false,
    ...extra,
  }
}

export function scoreFormReport(report, error) {
  if (error) return blankScore({ error: String(error) })
  if (!report) return blankScore({ pending: true })
  const summary = report.summary || {}
  const centered = Number(summary.centered) || 0
  const low = Number(summary.low) || 0
  const high = Number(summary.high) || 0
  const unavailable = Number(summary.unavailable) || 0
  const available = centered + low + high
  const glance = String(report.glance || '')
  const sampleShort = SAMPLE_GLANCES.has(glance) || (available === 0 && unavailable > 0)
  return {
    ok: true,
    pending: false,
    score: centered,
    low,
    high,
    skew: low + high,
    available,
    unavailable,
    glance,
    specialNote: specialNote(report.special_metrics),
    error: '',
    sampleShort,
  }
}

export function isSkewed(scored, minCentered) {
  if (!scored?.ok || scored.sampleShort || !scored.available) return false
  const floor = minCentered == null ? defaultMinCentered(scored.available) : minCentered
  if (!Number.isInteger(floor) || floor < 0) return false
  return scored.score < floor
}

export function formRankBadge(scored, skewed) {
  if (!scored || scored.pending) return { text: '待打分', tone: 'badge-muted' }
  if (!scored.ok) return { text: '失败', tone: 'badge-warn' }
  if (scored.sampleShort) return { text: '样本不足', tone: 'badge-muted' }
  if (skewed) return { text: '偏态', tone: 'badge-warn' }
  if (scored.available && scored.score === scored.available) return { text: '居中', tone: 'badge-ok' }
  return { text: '尚可', tone: 'badge-info' }
}

export function formRankCounts(scored) {
  if (!scored?.ok) return ''
  const parts = [`居中 ${scored.score}`, `偏低 ${scored.low}`, `偏高 ${scored.high}`]
  if (scored.unavailable) parts.push(`暂无 ${scored.unavailable}`)
  return parts.join(' · ')
}

function addedTime(value) {
  const time = Date.parse(value || '')
  return Number.isFinite(time) ? time : Number.POSITIVE_INFINITY
}

function sortGroup(scored) {
  if (scored?.pending) return 2
  if (!scored?.ok) return 3
  if (scored.sampleShort) return 1
  return 0
}

function compareRank(left, right, direction) {
  const group = sortGroup(left.scored) - sortGroup(right.scored)
  if (group) return group
  const leftScore = left.scored.score
  const rightScore = right.scored.score
  if (leftScore != null && rightScore != null && leftScore !== rightScore) {
    return (leftScore - rightScore) * direction
  }
  const leftSkew = left.scored.skew
  const rightSkew = right.scored.skew
  if (leftSkew != null && rightSkew != null && leftSkew !== rightSkew) return leftSkew - rightSkew
  const time = addedTime(left.addedAt) - addedTime(right.addedAt)
  if (time) return time
  return left.index - right.index
}

export function rankFormRows(rows, order = 'desc') {
  const direction = order === 'asc' ? 1 : -1
  return (rows || []).map((row, index) => ({
    ...row,
    index: row.index ?? index,
    scored: row.scored || scoreFormReport(row.report, row.error),
  })).sort((left, right) => compareRank(left, right, direction))
}

export function ticketLabel(item) {
  const main = (item?.numbers?.main || []).join(' ')
  const special = (item?.numbers?.special || []).filter(Boolean)
  return special.length ? `${main} + ${special.join(' ')}` : main
}

function entryOf(reports, id) {
  const entry = reports?.[id]
  if (!entry) return { report: null, error: '' }
  if (typeof entry.error === 'string' && entry.error && !entry.report && !entry.summary) {
    return { report: null, error: entry.error }
  }
  if (entry.report || entry.error) return { report: entry.report || null, error: entry.error || '' }
  return { report: entry, error: '' }
}

function summaryText({ total, ready, failed, pending, skewed, threshold }) {
  if (!total) return '当前彩种篮是空的，先放进号码再打分。'
  if (!ready && !failed) return `当前 ${total} 注，还没打分。`
  const parts = [`当前 ${total} 注`]
  if (ready) parts.push(`已打分 ${ready}`)
  if (failed) parts.push(`失败 ${failed}`)
  if (pending) parts.push(`待打分 ${pending}`)
  const head = parts.join('，')
  if (!threshold.ok) return `${head}。最低居中项数无效，先改好再看偏态。`
  if (threshold.value == null) return `${head}。低于各自满分一半的有 ${skewed} 注。`
  return `${head}。居中项少于 ${threshold.value} 的有 ${skewed} 注。`
}

export function buildFormRank(items, lotteryType, reports, options = {}) {
  const source = (items || []).filter((item) => item && item.lottery_type === lotteryType)
  const threshold = parseMinCentered(options.minCentered)
  const prepared = source.map((item, index) => {
    const entry = entryOf(reports, item.id)
    const scored = scoreFormReport(entry.report, entry.error)
    return {
      id: item.id,
      addedAt: item.added_at || item.addedAt || '',
      label: ticketLabel(item),
      numbers: item.numbers,
      index,
      scored,
      skewed: Boolean(threshold.ok && isSkewed(scored, threshold.value)),
    }
  })
  const rows = rankFormRows(prepared, options.order || 'desc').map((row) => ({
    ...row,
    badge: formRankBadge(row.scored, row.skewed),
    counts: formRankCounts(row.scored),
  }))
  const skewedIds = prepared.filter((row) => row.skewed).map((row) => row.id)
  const ready = prepared.filter((row) => row.scored.ok).length
  const failed = prepared.filter((row) => !row.scored.ok && !row.scored.pending).length
  const pending = prepared.filter((row) => row.scored.pending).length
  const summary = {
    total: prepared.length,
    ready,
    failed,
    pending,
    skewed: threshold.ok ? skewedIds.length : 0,
    text: '',
  }
  summary.text = summaryText({ ...summary, threshold })
  return { rows, skewedIds, threshold, summary }
}

export function formRankRemovalIds(items, lotteryType, checkedIds) {
  const wanted = new Set(checkedIds || [])
  const seen = new Set()
  const ids = []
  for (const item of items || []) {
    if (!item || item.lottery_type !== lotteryType) continue
    if (!item.id || seen.has(item.id) || !wanted.has(item.id)) continue
    seen.add(item.id)
    ids.push(item.id)
  }
  return ids
}

export function formRankRemovalPreview(rows, checkedIds, limit = 8) {
  const wanted = new Set(checkedIds || [])
  const ids = []
  const labels = []
  for (const row of rows || []) {
    if (!row?.id || !wanted.has(row.id) || ids.includes(row.id)) continue
    ids.push(row.id)
    if (row.label) labels.push(row.label)
  }
  const shown = labels.slice(0, limit)
  const hidden = Math.max(0, labels.length - shown.length)
  let text = ids.length ? `将移出 ${ids.length} 注` : '没有勾选要移出的注'
  if (shown.length) text += `：${shown.join('；')}`
  if (hidden) text += `；还有 ${hidden} 注`
  return { ids, count: ids.length, labels, shown, hidden, text }
}

export function reportsFromBatch(ids, body) {
  const found = new Map()
  for (const item of body?.items || []) {
    if (item?.id) found.set(String(item.id), item)
  }
  const map = {}
  for (const id of ids || []) {
    const item = found.get(String(id))
    if (!item || item.ok === false || !item.report) {
      map[id] = { error: item?.error || '没有返回这注' }
      continue
    }
    map[id] = { report: item.report }
  }
  return map
}

export async function scoreBasketTickets(tickets, requestBatch, options = {}) {
  const limit = options.limit ?? FORM_RANK_LIMIT
  const chunkSize = Math.max(1, Number(options.chunkSize) || 40)
  const map = {}
  const list = tickets || []
  for (let start = 0; start < list.length; start += chunkSize) {
    const chunk = list.slice(start, start + chunkSize)
    try {
      const body = await requestBatch({ tickets: chunk, limit })
      Object.assign(map, reportsFromBatch(chunk.map((item) => item.id), body))
    } catch (err) {
      const message = err?.message || '打分失败'
      for (const ticket of chunk) {
        if (ticket?.id) map[ticket.id] = { error: message }
      }
    }
  }
  return map
}
