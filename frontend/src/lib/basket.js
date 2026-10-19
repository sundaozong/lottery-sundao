export const BASKET_STORAGE_KEY = 'yysg.pick.basket'

export const BASKET_DISCLAIMER = '选号篮仅供娱乐，不构成投注建议。'

const HOLE_LIMIT = 24

const SOURCE_LABELS = {
  predict: '预测',
  manual: '手选',
  analysis: '回声',
  form: '体检',
}

const STRATEGY_LABELS = {
  hot: '热号',
  cold: '冷号',
  hybrid: '混合',
  random: '随机',
  pulse: '脉动综合',
}

const PROFILES = {
  ssq: { mode: 'set', name: '双色球', mainLo: 1, mainHi: 33, mainCount: 6, specLo: 1, specHi: 16, specCount: 1, width: 2, mainColor: 'red', specialColor: 'blue', specialLabel: '蓝球' },
  dlt: { mode: 'set', name: '大乐透', mainLo: 1, mainHi: 35, mainCount: 5, specLo: 1, specHi: 12, specCount: 2, width: 2, mainColor: 'red', specialColor: 'blue', specialLabel: '后区' },
  qlc: { mode: 'set', name: '七乐彩', mainLo: 1, mainHi: 30, mainCount: 7, specCount: 0, width: 2, mainColor: 'red', specialLabel: '' },
  kl8: { mode: 'set', name: '快乐八', mainLo: 1, mainHi: 80, mainMin: 1, mainMax: 20, manualMin: 1, manualMax: 10, specCount: 0, width: 2, mainColor: 'orange', specialLabel: '' },
  fc3d: { mode: 'digit', name: '福彩3D', mainLo: 0, mainHi: 9, mainCount: 3, specCount: 0, width: 1, mainColor: 'green', positions: ['百', '十', '个'] },
  pl3: { mode: 'digit', name: '排列三', mainLo: 0, mainHi: 9, mainCount: 3, specCount: 0, width: 1, mainColor: 'green', positions: ['百', '十', '个'] },
  pl5: { mode: 'digit', name: '排列五', mainLo: 0, mainHi: 9, mainCount: 5, specCount: 0, width: 1, mainColor: 'green', positions: ['万', '千', '百', '十', '个'] },
  qxc: { mode: 'digit', name: '七星彩', mainLo: 0, mainHi: 9, mainCount: 6, specLo: 0, specHi: 14, specCount: 1, width: 1, mainColor: 'purple', specialColor: 'orange', specialLabel: '特别号', positions: ['1', '2', '3', '4', '5', '6'] },
}

let idSeq = 0

function makeId() {
  idSeq += 1
  return `b${Date.now().toString(36)}${idSeq.toString(36)}`
}

function tokens(value) {
  if (value == null) return []
  const raw = Array.isArray(value) ? value : String(value).trim().split(/[\s,，]+/)
  return raw.map((item) => String(item).trim()).filter(Boolean)
}

function formatBall(raw, lo, hi, width) {
  const text = String(raw).trim()
  if (!/^\d+$/.test(text)) return null
  const number = Number(text)
  if (number < lo || number > hi) return null
  return width > 1 ? String(number).padStart(width, '0') : String(number)
}

function takeBalls(values, lo, hi, width, exact, min, max, label, allowDup = false) {
  const balls = []
  const seen = new Set()
  for (const raw of tokens(values)) {
    const ball = formatBall(raw, lo, hi, width)
    if (!ball) return { ok: false, message: `${label}超出范围或不是数字` }
    if (seen.has(ball) && !allowDup) return { ok: false, message: `${label}重复：${ball}` }
    seen.add(ball)
    balls.push(ball)
  }
  if (exact != null && balls.length !== exact) {
    return { ok: false, message: `${label}需要 ${exact} 个` }
  }
  if (min != null && balls.length < min) return { ok: false, message: `${label}至少 ${min} 个` }
  if (max != null && balls.length > max) return { ok: false, message: `${label}最多 ${max} 个` }
  return { ok: true, balls }
}

export function basketProfile(lotteryType) {
  return PROFILES[lotteryType] || null
}

export function normalizeNumbers(lotteryType, numbers) {
  const profile = PROFILES[lotteryType]
  if (!profile) return { ok: false, message: '未知彩种' }
  const source = numbers || {}
  const main = takeBalls(
    source.main,
    profile.mainLo,
    profile.mainHi,
    profile.width,
    profile.mainCount,
    profile.mainMin,
    profile.mainMax,
    profile.mode === 'digit' ? '号码' : '主号',
    profile.mode === 'digit',
  )
  if (!main.ok) return main
  const specialValues = tokens(source.special)
  if (!profile.specCount) {
    if (specialValues.length) return { ok: false, message: '该彩种没有特别号' }
    const ordered = profile.mode === 'set'
      ? [...main.balls].sort((a, b) => Number(a) - Number(b))
      : main.balls
    return { ok: true, numbers: { main: ordered, special: [] } }
  }
  const special = takeBalls(
    specialValues,
    profile.specLo,
    profile.specHi,
    profile.width,
    profile.specCount,
    null,
    null,
    profile.specialLabel || '特别号',
  )
  if (!special.ok) return special
  const orderedMain = profile.mode === 'set'
    ? [...main.balls].sort((a, b) => Number(a) - Number(b))
    : main.balls
  const orderedSpecial = profile.mode === 'set'
    ? [...special.balls].sort((a, b) => Number(a) - Number(b))
    : special.balls
  return { ok: true, numbers: { main: orderedMain, special: orderedSpecial } }
}

export function numberSignature(lotteryType, numbers) {
  const parsed = normalizeNumbers(lotteryType, numbers)
  if (!parsed.ok) return ''
  return `${lotteryType}|${parsed.numbers.main.join(',')}|${parsed.numbers.special.join(',')}`
}

export function addToBasket(items, draft, options = {}) {
  const parsed = normalizeNumbers(draft?.lottery_type, draft?.numbers)
  if (!parsed.ok) return { items, status: 'invalid', message: parsed.message }
  const sig = numberSignature(draft.lottery_type, parsed.numbers)
  if ((items || []).some((item) => numberSignature(item.lottery_type, item.numbers) === sig)) {
    return { items, status: 'duplicate', message: '这注已在选号篮里' }
  }
  const item = {
    id: options.id || makeId(),
    lottery_type: draft.lottery_type,
    numbers: parsed.numbers,
    source: draft.source || 'manual',
    strategy: draft.strategy || '',
    note: draft.note || '',
    added_at: options.now || new Date().toISOString(),
  }
  return { items: [...(items || []), item], status: 'added', item, message: '已放入选号篮' }
}

export function addManyToBasket(items, drafts, options = {}) {
  let next = items || []
  let added = 0
  let duplicates = 0
  const invalid = []
  ;(drafts || []).forEach((draft, index) => {
    const result = addToBasket(next, draft, {
      now: options.now,
      id: options.ids ? options.ids[index] : undefined,
    })
    next = result.items
    if (result.status === 'added') added += 1
    else if (result.status === 'duplicate') duplicates += 1
    else invalid.push(result.message)
  })
  return { items: next, added, duplicates, invalid }
}

export function removeFromBasket(items, id) {
  return (items || []).filter((item) => item.id !== id)
}

export function clearLottery(items, lotteryType) {
  return (items || []).filter((item) => item.lottery_type !== lotteryType)
}

export function clearBasket() {
  return []
}

export function itemsForLottery(items, lotteryType) {
  return (items || []).filter((item) => item.lottery_type === lotteryType)
}

function isStoredItem(item) {
  return Boolean(item && item.id && PROFILES[item.lottery_type] && Array.isArray(item.numbers?.main) && item.numbers.main.length)
}

export function loadBasket(storage) {
  try {
    const raw = storage.getItem(BASKET_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isStoredItem)
  } catch {
    return []
  }
}

export function saveBasket(storage, items) {
  storage.setItem(BASKET_STORAGE_KEY, JSON.stringify(items || []))
}

function comb(n, k) {
  if (k < 0 || k > n) return 0
  const use = Math.min(k, n - k)
  let result = 1
  for (let i = 1; i <= use; i += 1) result = (result * (n - use + i)) / i
  return Math.round(result)
}

function kl8Pick(length) {
  if (length <= 10) return length
  return 10
}

export function betCount(lotteryType, numbers) {
  const parsed = normalizeNumbers(lotteryType, numbers)
  if (!parsed.ok) return 0
  if (lotteryType === 'kl8') return comb(parsed.numbers.main.length, kl8Pick(parsed.numbers.main.length))
  return 1
}

export function lineCost(lotteryType, numbers, multiple = 1, unit = 2) {
  const times = Math.max(1, Math.floor(Number(multiple) || 1))
  return betCount(lotteryType, numbers) * unit * times
}

function noteFor(item) {
  const parts = [
    '选号篮',
    SOURCE_LABELS[item.source] || item.source,
    STRATEGY_LABELS[item.strategy] || item.strategy,
    item.note,
  ]
  return parts.filter(Boolean).join(' · ')
}

function recordNumbers(item, multiple) {
  const { main, special } = item.numbers
  if (item.lottery_type === 'kl8') {
    return { play: 'pick', pick: kl8Pick(main.length), main, special: [], multiple }
  }
  const profile = PROFILES[item.lottery_type]
  if (profile?.mode === 'digit') {
    const positions = main.map((n) => [n])
    if (profile.specCount) positions.push([...(special || []).slice(0, profile.specCount)])
    return {
      play: item.lottery_type === 'qxc' ? 'single' : 'direct',
      main,
      special: special || [],
      positions,
      multiple,
    }
  }
  return { play: 'single', main, special: special || [], multiple }
}

export function recordBody(item, options = {}) {
  const multiple = Math.max(1, Math.floor(Number(options.multiple) || 1))
  return {
    lottery_type: item.lottery_type,
    issue: String(options.issue ?? '').trim(),
    numbers: recordNumbers(item, multiple),
    cost: lineCost(item.lottery_type, item.numbers, multiple),
    prize: 0,
    note: noteFor(item),
    purchased_at: options.today || new Date().toISOString().slice(0, 10),
  }
}

export async function writeBasketRecords(items, createRecord, options = {}) {
  const createdIds = []
  const errors = []
  for (const item of items || []) {
    try {
      await createRecord(recordBody(item, options))
      createdIds.push(item.id)
    } catch (err) {
      errors.push({ id: item.id, message: err?.message || '写入失败' })
    }
  }
  return { createdIds, errors }
}

function pairOverlap(profile, left, right) {
  if (profile.mode === 'digit') {
    let count = 0
    const positions = []
    left.main.forEach((n, index) => {
      if (n === right.main[index]) {
        count += 1
        positions.push(index)
      }
    })
    return { count, positions }
  }
  const rightSet = new Set(right.main)
  const shared = left.main.filter((n) => rightSet.has(n))
  return { count: shared.length, positions: [] }
}

function wasteHint(profile, overlap, leftLen, rightLen) {
  if (!overlap) return profile.mode === 'digit' ? '同位没有撞号' : '主号没有撞'
  const smaller = Math.min(leftLen, rightLen) || 1
  const threshold = Math.max(2, Math.ceil(smaller / 2))
  const text = profile.mode === 'digit' ? `同位撞了 ${overlap} 个` : `主号撞了 ${overlap} 个`
  return overlap >= threshold ? `浪费偏多：${text}` : text
}

function repeatedMain(profile, tickets) {
  if (profile.mode === 'digit') {
    const counts = new Map()
    tickets.forEach((ticket) => {
      ticket.main.forEach((n, position) => {
        const key = `${position}:${n}`
        const prev = counts.get(key) || { n, count: 0, position, positionLabel: profile.positions?.[position] || String(position + 1) }
        prev.count += 1
        counts.set(key, prev)
      })
    })
    return [...counts.values()]
      .filter((hit) => hit.count >= 2)
      .sort((a, b) => a.position - b.position || Number(a.n) - Number(b.n))
  }
  const counts = new Map()
  tickets.forEach((ticket) => {
    for (const n of new Set(ticket.main)) counts.set(n, (counts.get(n) || 0) + 1)
  })
  return [...counts.entries()]
    .filter(([, count]) => count >= 2)
    .map(([n, count]) => ({ n, count, position: null, positionLabel: '' }))
    .sort((a, b) => Number(a.n) - Number(b.n))
}

function repeatedSpecial(tickets) {
  const counts = new Map()
  tickets.forEach((ticket) => {
    for (const n of new Set(ticket.special || [])) counts.set(n, (counts.get(n) || 0) + 1)
  })
  return [...counts.entries()]
    .filter(([, count]) => count >= 2)
    .map(([n, count]) => ({ n, count }))
    .sort((a, b) => Number(a.n) - Number(b.n))
}

function uncovered(profile, tickets) {
  if (profile.mode !== 'set') return { holes: [], truncated: false }
  const covered = new Set(tickets.flatMap((ticket) => ticket.main))
  const holes = []
  let truncated = false
  for (let n = profile.mainLo; n <= profile.mainHi; n += 1) {
    const key = profile.width > 1 ? String(n).padStart(profile.width, '0') : String(n)
    if (covered.has(key)) continue
    if (holes.length >= HOLE_LIMIT) {
      truncated = true
      break
    }
    holes.push(key)
  }
  return { holes, truncated }
}

function collisionSummary(profile, tickets, mains, specials, holes, truncated) {
  if (tickets.length < 2) return '篮里不足 2 注，先放两注再看撞号。'
  let text = `共 ${tickets.length} 注，${mains.length} 个主号被重复选中`
  if (specials.length) text += `，另有 ${specials.length} 个特别号被重复选中`
  if (profile.mode === 'set') {
    if (!holes.length) text += '。主号池已经铺满'
    else if (truncated) text += `。没选到的号很多，这里只列 ${holes.length} 个`
    else text += `。还有 ${holes.length} 个主号没选到`
  } else if (mains.length) {
    text += '。同位相同才算撞号'
  }
  return text
}

export function basketCollision(lotteryType, items) {
  const profile = PROFILES[lotteryType]
  const tickets = itemsForLottery(items, lotteryType).map((item) => item.numbers)
  if (!profile) {
    return {
      mode: '',
      ticketCount: 0,
      repeatedMain: [],
      repeatedSpecial: [],
      holes: [],
      pairs: [],
      summary: '未知彩种',
      disclaimer: BASKET_DISCLAIMER,
    }
  }
  const mains = tickets.length >= 2 ? repeatedMain(profile, tickets) : []
  const specials = tickets.length >= 2 ? repeatedSpecial(tickets) : []
  const holes = tickets.length >= 2 ? uncovered(profile, tickets) : { holes: [], truncated: false }
  const pairs = []
  if (tickets.length >= 2) {
    for (let left = 0; left < tickets.length; left += 1) {
      for (let right = left + 1; right < tickets.length; right += 1) {
        const overlap = pairOverlap(profile, tickets[left], tickets[right])
        pairs.push({
          left: left + 1,
          right: right + 1,
          overlapCount: overlap.count,
          positions: overlap.positions,
          waste: wasteHint(profile, overlap.count, tickets[left].main.length, tickets[right].main.length),
        })
      }
    }
  }
  return {
    mode: profile.mode,
    ticketCount: tickets.length,
    repeatedMain: mains,
    repeatedSpecial: specials,
    holes: holes.holes,
    holesTruncated: holes.truncated,
    pairs,
    summary: collisionSummary(profile, tickets, mains, specials, holes.holes, holes.truncated),
    disclaimer: BASKET_DISCLAIMER,
  }
}

export function formatBasketText(items, lotteryType) {
  const rows = itemsForLottery(items, lotteryType)
  if (!rows.length) return ''
  const profile = PROFILES[lotteryType]
  const lines = [profile?.name || lotteryType]
  for (const item of rows) {
    const main = item.numbers.main.join(' ')
    const special = item.numbers.special?.length ? ` + ${item.numbers.special.join(' ')}` : ''
    lines.push(`${main}${special}`)
  }
  lines.push(BASKET_DISCLAIMER)
  return lines.join('\n')
}

export function sourceLabel(item) {
  const parts = [SOURCE_LABELS[item?.source] || item?.source || '', STRATEGY_LABELS[item?.strategy] || item?.strategy || '']
  return parts.filter(Boolean).join(' · ')
}
