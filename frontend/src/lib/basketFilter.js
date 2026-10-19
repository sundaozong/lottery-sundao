import { basketProfile } from './basket.js'

export const BASKET_FILTER_DISCLAIMER = '过滤仅供整理号码，不构成投注建议。'

const RANGE_KEYS = ['sum', 'span', 'odd', 'hewei', 'ac']

export function emptyBasketFilter() {
  return {
    sumMin: '',
    sumMax: '',
    spanMin: '',
    spanMax: '',
    oddMin: '',
    oddMax: '',
    heweiMin: '',
    heweiMax: '',
    acMin: '',
    acMax: '',
  }
}

function mainValues(lotteryType, numbers) {
  const profile = basketProfile(lotteryType)
  if (!profile) return null
  const raw = Array.isArray(numbers) ? numbers : numbers?.main
  if (!Array.isArray(raw)) return null
  const values = []
  const seen = new Set()
  for (const item of raw) {
    const text = String(item ?? '').trim()
    if (!/^\d+$/.test(text)) continue
    const number = Number(text)
    if (profile.mode === 'set') {
      if (seen.has(number)) continue
      seen.add(number)
    }
    values.push(number)
  }
  return values.length ? values : null
}

function acOf(values) {
  if (values.length < 2) return null
  const ordered = [...values].sort((left, right) => left - right)
  const diffs = new Set()
  for (let index = 0; index < ordered.length; index += 1) {
    for (let next = index + 1; next < ordered.length; next += 1) {
      diffs.add(Math.abs(ordered[next] - ordered[index]))
    }
  }
  return diffs.size - (ordered.length - 1)
}

export function ticketMetrics(lotteryType, numbers) {
  const values = mainValues(lotteryType, numbers)
  if (!values) return null
  const sum = values.reduce((total, number) => total + number, 0)
  return {
    sum,
    span: Math.max(...values) - Math.min(...values),
    odd: values.reduce((count, number) => count + (number % 2 === 1 ? 1 : 0), 0),
    hewei: sum % 10,
    ac: acOf(values),
  }
}

function bound(value) {
  if (value == null) return null
  if (typeof value === 'string' && value.trim() === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function filterIsActive(filter) {
  return RANGE_KEYS.some((key) => bound(filter?.[`${key}Min`]) != null || bound(filter?.[`${key}Max`]) != null)
}

function inRange(value, min, max) {
  if (value == null || Number.isNaN(value)) return false
  if (min != null && value < min) return false
  if (max != null && value > max) return false
  return true
}

export function matchFilter(metrics, filter) {
  if (!filterIsActive(filter)) return true
  if (!metrics) return false
  for (const key of RANGE_KEYS) {
    const min = bound(filter?.[`${key}Min`])
    const max = bound(filter?.[`${key}Max`])
    if (min == null && max == null) continue
    if (min != null && max != null && min > max) return false
    if (!inRange(metrics[key], min, max)) return false
  }
  return true
}

function ticketLabel(item) {
  const main = (item?.numbers?.main || []).join(' ')
  const special = (item?.numbers?.special || []).filter(Boolean)
  return special.length ? `${main} + ${special.join(' ')}` : main
}

function rowOf(item, lotteryType) {
  return {
    id: item.id,
    item,
    label: ticketLabel(item),
    metrics: ticketMetrics(lotteryType, item.numbers),
  }
}

function summaryText(total, keep, drop, active) {
  if (!total) return '当前彩种篮是空的，先放进号码再过滤。'
  if (!active) return `当前 ${total} 注，还没设条件，全部保留。`
  return `当前 ${total} 注 → 保留 ${keep}、剔除 ${drop}`
}

export function previewBasketFilter(items, lotteryType, filter) {
  const rows = (items || []).filter((item) => item?.lottery_type === lotteryType)
  const active = filterIsActive(filter)
  const keep = []
  const drop = []
  rows.forEach((item) => {
    const row = rowOf(item, lotteryType)
    if (matchFilter(row.metrics, filter)) keep.push(row)
    else drop.push(row)
  })
  return {
    keepIds: keep.map((row) => row.id),
    dropIds: drop.map((row) => row.id),
    keep,
    drop,
    summary: {
      total: rows.length,
      keep: keep.length,
      drop: drop.length,
      active,
      text: summaryText(rows.length, keep.length, drop.length, active),
    },
  }
}

export function applyBasketFilter(items, lotteryType, filter) {
  const preview = previewBasketFilter(items, lotteryType, filter)
  if (!preview.summary.active || !preview.dropIds.length) {
    return { items: [...(items || [])], removed: [], removedCount: 0, preview }
  }
  const gone = new Set(preview.dropIds)
  return {
    items: (items || []).filter((item) => !gone.has(item.id)),
    removed: preview.drop,
    removedCount: preview.dropIds.length,
    preview,
  }
}

export function filterFromBands(bands) {
  const next = {}
  for (const key of ['sum', 'span', 'odd']) {
    const band = bands?.[key]
    if (band?.low == null || band?.high == null) continue
    next[`${key}Min`] = band.low
    next[`${key}Max`] = band.high
  }
  return next
}
