import { recordBody } from './basket.js'

export function ticketsFromBasket(items, multiple = 1) {
  const times = Math.max(1, Math.floor(Number(multiple) || 1))
  return (items || []).map((item) => {
    const numbers = recordBody(item, { multiple: times, issue: '' }).numbers
    const ticket = {
      id: item?.id ?? null,
      numbers,
      play: numbers.play || null,
    }
    if (numbers.pick != null) ticket.pick = numbers.pick
    return ticket
  })
}

function asList(value) {
  return Array.isArray(value) ? value.map((n) => String(n)) : []
}

function setFlags(mine, other) {
  const counts = new Map()
  for (const n of other) counts.set(n, (counts.get(n) || 0) + 1)
  return mine.map((n) => {
    const left = counts.get(n) || 0
    if (!left) return false
    counts.set(n, left - 1)
    return true
  })
}

function positionalDigits(type, draw) {
  const positions = draw?.positions || []
  if (positions.some((pos) => (pos || []).length)) {
    return positions.map((pos) => String((pos || [])[0] ?? ''))
  }
  if (type === 'qxc') return [...asList(draw?.main), ...asList(draw?.special)]
  return asList(draw?.main)
}

export function betHitView(lotteryType, bet, draw) {
  const source = bet || {}
  const opened = draw || {}
  const positions = Array.isArray(source.positions) ? source.positions : []
  if (positions.some((pos) => (pos || []).length)) {
    const digits = positionalDigits(lotteryType, opened)
    const betPos = positions.map((pos) => asList(pos))
    const specialIndex = lotteryType === 'qxc' ? betPos.length - 1 : -1
    let count = 0
    const hitMain = []
    const hitSpecial = []
    betPos.forEach((pos, index) => {
      for (const n of pos) {
        if (n !== digits[index]) continue
        count += 1
        if (index === specialIndex) hitSpecial.push(n)
        else hitMain.push(n)
      }
    })
    return {
      count,
      hits: { main: hitMain, special: hitSpecial },
      numbers: { positions: betPos },
      marks: { positions: betPos.map((pos, index) => pos.map((n) => n === digits[index])) },
    }
  }

  const betMain = asList(source.main)
  const betSpecial = asList(source.special)
  const drawMain = asList(opened.main)
  const drawSpecial = asList(opened.special)
  if (lotteryType === 'qlc') {
    const basic = new Set(drawMain)
    const special = new Set(drawSpecial)
    const marks = { main: betMain.map((n) => basic.has(n) || special.has(n)) }
    const hits = {
      main: betMain.filter((n) => basic.has(n)),
      special: betMain.filter((n) => special.has(n)),
    }
    return {
      count: hits.main.length + hits.special.length,
      hits,
      numbers: { main: betMain, special: [] },
      marks,
    }
  }

  const marks = {
    main: setFlags(betMain, drawMain),
    special: setFlags(betSpecial, drawSpecial),
  }
  return {
    count: marks.main.filter(Boolean).length + marks.special.filter(Boolean).length,
    hits: {
      main: betMain.filter((_, index) => marks.main[index]),
      special: betSpecial.filter((_, index) => marks.special[index]),
    },
    numbers: { main: betMain, special: betSpecial },
    marks,
  }
}

export function formatMoney(value) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  if (Number.isInteger(amount)) return `¥ ${amount}`
  return `¥ ${amount.toFixed(2)}`
}

export function formatSignedMoney(value) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  const text = formatMoney(Math.abs(amount))
  if (amount > 0) return `+${text}`
  if (amount < 0) return `-${text}`
  return text
}

export function isIllustrativeWin(item) {
  return item?.status === 'ok' && Number(item.amount) > 0
}

export function netClass(net) {
  const amount = Number(net)
  if (!Number.isFinite(amount) || amount === 0) return ''
  return amount > 0 ? 'ok' : 'down'
}

export function verifyStatusText(item) {
  if (!item) return ''
  if (item.status === 'no_draw') return '无开奖'
  if (item.status === 'error') return item.message || '无法计算'
  return item.level || (Number(item.amount) > 0 ? '示意中奖' : '未中奖')
}
