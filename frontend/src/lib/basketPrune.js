import { basketProfile, normalizeNumbers } from './basket.js'

export const BASKET_PRUNE_DISCLAIMER = '仅供整理号码，不构成投注建议。'

const LOTTERY_TYPES = ['ssq', 'dlt', 'qlc', 'kl8', 'fc3d', 'pl3', 'pl5', 'qxc']

export function defaultPruneThreshold(profile) {
  if (!profile) return 2
  const count = Number(profile.mainCount) || Number(profile.manualMax) || Number(profile.mainMax) || 2
  return Math.max(2, count - 1)
}

function lotteryTypeOf(profile) {
  if (!profile) return ''
  return LOTTERY_TYPES.find((type) => basketProfile(type) === profile) || ''
}

function resolveThreshold(profile, threshold) {
  if (typeof threshold === 'string' && threshold.trim() === '') return defaultPruneThreshold(profile)
  if (threshold == null) return defaultPruneThreshold(profile)
  const number = typeof threshold === 'string' ? Number(threshold.trim()) : Number(threshold)
  if (!Number.isInteger(number) || number < 1) return defaultPruneThreshold(profile)
  return number
}

function normalized(profile, numbers) {
  const lotteryType = lotteryTypeOf(profile)
  if (!lotteryType) return null
  const parsed = normalizeNumbers(lotteryType, numbers)
  return parsed.ok ? parsed.numbers : null
}

function countOverlap(profile, left, right) {
  if (profile.mode === 'digit') {
    const length = Math.min(left.length, right.length)
    let count = 0
    for (let index = 0; index < length; index += 1) {
      if (left[index] === right[index]) count += 1
    }
    return count
  }
  const rightSet = new Set(right)
  const seen = new Set()
  let count = 0
  for (const ball of left) {
    if (seen.has(ball)) continue
    seen.add(ball)
    if (rightSet.has(ball)) count += 1
  }
  return count
}

function ticketLabel(numbers) {
  const main = (numbers?.main || []).join(' ')
  const special = (numbers?.special || []).filter(Boolean)
  return special.length ? `${main} + ${special.join(' ')}` : main
}

function summaryText(total, keep, remove, threshold, specialPairs) {
  if (total < 2) return '篮里不足 2 注，先放两注再修剪。'
  if (!remove) return `当前 ${total} 注，重合不少于 ${threshold} 时没有近重复，全部保留。`
  let text = `当前 ${total} 注 → 保留 ${keep}、移出 ${remove}（重合不少于 ${threshold}）`
  if (specialPairs) text += `。另有 ${specialPairs} 对特别号也重合，只作参考`
  return text
}

function emptyResult(text, threshold = null) {
  return {
    keepIds: [],
    removeIds: [],
    pairsOver: [],
    remove: [],
    summary: {
      total: 0,
      keep: 0,
      remove: 0,
      threshold,
      ready: false,
      specialPairs: 0,
      text,
    },
  }
}

export function pruneBasket(tickets, profile, threshold) {
  if (!profile) return emptyResult('未知彩种')
  const rows = Array.isArray(tickets) ? tickets : []
  const limit = resolveThreshold(profile, threshold)
  if (rows.length < 2) {
    return {
      keepIds: rows.map((item) => item.id),
      removeIds: [],
      pairsOver: [],
      remove: [],
      summary: {
        total: rows.length,
        keep: rows.length,
        remove: 0,
        threshold: limit,
        ready: false,
        specialPairs: 0,
        text: summaryText(rows.length, rows.length, 0, limit, 0),
      },
    }
  }

  const numbers = rows.map((item) => normalized(profile, item.numbers))
  const overlap = rows.map(() => rows.map(() => 0))
  const specialOverlap = rows.map(() => rows.map(() => 0))
  for (let left = 0; left < rows.length; left += 1) {
    for (let right = left + 1; right < rows.length; right += 1) {
      if (!numbers[left] || !numbers[right]) continue
      overlap[left][right] = countOverlap(profile, numbers[left].main, numbers[right].main)
      overlap[right][left] = overlap[left][right]
      specialOverlap[left][right] = countOverlap(profile, numbers[left].special || [], numbers[right].special || [])
      specialOverlap[right][left] = specialOverlap[left][right]
    }
  }

  const remaining = new Set(rows.map((_, index) => index))
  const removedAt = []
  for (let step = 0; step < rows.length; step += 1) {
    let best = null
    for (const index of remaining) {
      let degree = 0
      for (const other of remaining) {
        if (other !== index && overlap[index][other] >= limit) degree += 1
      }
      if (!degree) continue
      const id = String(rows[index].id ?? '')
      const better = !best
        || degree > best.degree
        || (degree === best.degree && index > best.index)
        || (degree === best.degree && index === best.index && id > best.id)
      if (better) best = { index, degree, id }
    }
    if (!best) break
    remaining.delete(best.index)
    removedAt.push(best.index)
  }

  const removed = new Set(removedAt)
  const keepIds = []
  const removeIds = []
  const remove = []
  rows.forEach((item, index) => {
    if (removed.has(index)) {
      removeIds.push(item.id)
      let maxOverlap = 0
      let links = 0
      for (let other = 0; other < rows.length; other += 1) {
        if (other === index) continue
        if (overlap[index][other] > maxOverlap) maxOverlap = overlap[index][other]
        if (overlap[index][other] >= limit) links += 1
      }
      remove.push({
        id: item.id,
        index: index + 1,
        label: ticketLabel(numbers[index] || item.numbers),
        maxOverlap,
        links,
      })
      return
    }
    keepIds.push(item.id)
  })

  const pairsOver = []
  for (let left = 0; left < rows.length; left += 1) {
    for (let right = left + 1; right < rows.length; right += 1) {
      if (overlap[left][right] < limit) continue
      pairsOver.push({
        leftId: rows[left].id,
        rightId: rows[right].id,
        left: left + 1,
        right: right + 1,
        overlap: overlap[left][right],
        specialOverlap: specialOverlap[left][right],
      })
    }
  }
  const specialPairs = pairsOver.filter((pair) => pair.specialOverlap > 0).length

  return {
    keepIds,
    removeIds,
    pairsOver,
    remove,
    summary: {
      total: rows.length,
      keep: keepIds.length,
      remove: removeIds.length,
      threshold: limit,
      ready: true,
      specialPairs,
      text: summaryText(rows.length, keepIds.length, removeIds.length, limit, specialPairs),
    },
  }
}

export function previewBasketPrune(items, lotteryType, threshold) {
  const profile = basketProfile(lotteryType)
  if (!profile) return emptyResult('未知彩种')
  const tickets = (items || []).filter((item) => item?.lottery_type === lotteryType)
  return pruneBasket(tickets, profile, threshold)
}
