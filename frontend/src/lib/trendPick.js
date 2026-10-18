import { basketProfile, normalizeNumbers } from './basket.js'

export function emptyTrendDraft() {
  return { main: [], special: [] }
}

function cloneDraft(draft) {
  return {
    main: [...(draft?.main || [])].map(String),
    special: [...(draft?.special || [])].map(String),
  }
}

function formatBall(raw, lo, hi, width) {
  const text = String(raw ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const number = Number(text)
  if (!Number.isInteger(number) || number < lo || number > hi) return null
  return width > 1 ? String(number).padStart(width, '0') : String(number)
}

export function trendRule(lotteryType) {
  const profile = basketProfile(lotteryType)
  if (!profile) return null
  const mainMax = profile.mainCount || profile.manualMax || profile.mainMax || 0
  const mainMin = profile.mainCount || profile.manualMin || profile.mainMin || mainMax
  return {
    mode: profile.mode,
    mainMax,
    mainMin,
    specMax: profile.specCount || 0,
    specMin: profile.specCount || 0,
    width: profile.width,
    mainLo: profile.mainLo,
    mainHi: profile.mainHi,
    specLo: profile.specLo,
    specHi: profile.specHi,
    positions: profile.positions || [],
    mainLabel: profile.mode === 'digit' ? '号码' : '主号',
    specialLabel: profile.specialLabel || '特别号',
    mainColor: profile.mainColor,
    specialColor: profile.specialColor || '',
  }
}

function targetOf(rule, zone) {
  if (zone === 'special') {
    if (!rule.specMax) return rule.mode === 'set' ? 'main' : null
    return 'special'
  }
  return 'main'
}

function bounds(rule, target) {
  if (target === 'special') return [rule.specLo, rule.specHi]
  return [rule.mainLo, rule.mainHi]
}

export function toggleTrendNumber(lotteryType, draft, zone, raw) {
  const next = cloneDraft(draft)
  const rule = trendRule(lotteryType)
  if (!rule) return { draft: next, status: 'invalid', message: '未知彩种' }
  const target = targetOf(rule, zone)
  if (!target) return { draft: next, status: 'invalid', message: '该彩种没有特别号' }
  const [lo, hi] = bounds(rule, target)
  const ball = formatBall(raw, lo, hi, rule.width)
  if (!ball) return { draft: next, status: 'invalid', message: '号码超出范围' }

  const list = next[target]
  const max = target === 'special' ? rule.specMax : rule.mainMax
  const allowDup = rule.mode === 'digit' && target === 'main'
  const count = list.filter((item) => item === ball).length
  const label = target === 'special' ? rule.specialLabel : rule.mainLabel

  if (max === 1) {
    next[target] = count ? [] : [ball]
    return { draft: next, status: count ? 'removed' : 'added', message: '' }
  }
  if (count > 0) {
    if (allowDup && list.length < max) {
      list.push(ball)
      return { draft: next, status: 'added', message: '' }
    }
    list.splice(list.lastIndexOf(ball), 1)
    return { draft: next, status: 'removed', message: '' }
  }
  if (max > 0 && list.length >= max) {
    return { draft: next, status: 'full', message: `${label}已满` }
  }
  list.push(ball)
  if (rule.mode === 'set') list.sort((a, b) => Number(a) - Number(b))
  return { draft: next, status: 'added', message: '' }
}

export function isTrendPicked(lotteryType, draft, zone, raw) {
  const rule = trendRule(lotteryType)
  if (!rule) return false
  const target = targetOf(rule, zone)
  if (!target) return false
  const [lo, hi] = bounds(rule, target)
  const ball = formatBall(raw, lo, hi, rule.width)
  if (!ball) return false
  return (draft?.[target] || []).map(String).includes(ball)
}

export function removeTrendAt(draft, zone, index) {
  const next = cloneDraft(draft)
  const key = zone === 'special' ? 'special' : 'main'
  if (!Number.isInteger(index) || index < 0 || index >= next[key].length) return next
  next[key].splice(index, 1)
  return next
}

export function trendDraftState(lotteryType, draft) {
  const rule = trendRule(lotteryType)
  const numbers = cloneDraft(draft)
  if (!rule) return { complete: false, message: '未知彩种', numbers }
  const { main, special } = numbers
  if (main.length > rule.mainMax) {
    const unit = rule.mode === 'digit' ? '位' : '个'
    return { complete: false, message: `${rule.mainLabel}最多 ${rule.mainMax} ${unit}`, numbers }
  }
  const gaps = []
  if (main.length < rule.mainMin) {
    const need = rule.mainMin - main.length
    gaps.push(rule.mode === 'digit' ? `还差 ${need} 位` : `${rule.mainLabel}还差 ${need} 个`)
  }
  if (rule.specMin && special.length < rule.specMin) {
    const need = rule.specMin - special.length
    gaps.push(need === rule.specMin ? `${rule.specialLabel}未选` : `${rule.specialLabel}还差 ${need} 个`)
  }
  if (gaps.length) return { complete: false, message: gaps.join('，'), numbers }
  const parsed = normalizeNumbers(lotteryType, numbers)
  if (!parsed.ok) return { complete: false, message: parsed.message, numbers }
  const roomy = rule.mainMax !== rule.mainMin && main.length < rule.mainMax
  const message = roomy ? `已选 ${main.length} 个，最多 ${rule.mainMax}` : '可以加入'
  return { complete: true, message, numbers: parsed.numbers }
}

export function omitHeatLevel(value, maxValue) {
  const n = Number(value)
  const max = Number(maxValue)
  if (!Number.isFinite(n) || n <= 0 || !Number.isFinite(max) || max <= 0) return 0
  if (n <= max / 3) return 1
  if (n <= (max * 2) / 3) return 2
  return 3
}

export function omitHeatMax(rows, key) {
  let max = 0
  for (const row of rows || []) {
    const map = row?.[key]
    if (!map || typeof map !== 'object') continue
    for (const value of Object.values(map)) {
      const n = Number(value)
      if (Number.isFinite(n) && n > max) max = n
    }
  }
  return max
}
