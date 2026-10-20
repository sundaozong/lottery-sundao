import {
  basketProfile,
  betCount,
  itemsForLottery,
  normalizeNumbers,
  sourceLabel,
} from './basket.js'

export const SLIP_UNIT_YUAN = 2

export const BASKET_SLIP_DISCLAIMER = '投注单只方便把号码带到投注站，不对照开奖，也不算奖金。不是脉动。仅供娱乐，不构成投注建议。'

export const BASKET_SLIP_EMPTY = '当前彩种篮是空的，先放进号码再导出投注单。'

const CSV_HEADER = 'index,numbers,source,note,stake'

function pad(value) {
  return String(value).padStart(2, '0')
}

function asDate(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value
  const parsed = value ? new Date(value) : new Date()
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed
}

function formatSlipWhen(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function compactStamp(date) {
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`
}

function csvCell(value) {
  const text = String(value ?? '')
  if (/[",\r\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`
  return text
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function lineText(row) {
  const remark = [row.source, row.note].filter(Boolean).join(' · ')
  return remark ? `${row.index} | ${row.numbers} | ${remark}` : `${row.index} | ${row.numbers}`
}

export function slipFilename(lotteryType, date, ext) {
  const when = asDate(date)
  const type = String(lotteryType || '').replace(/[^a-z0-9]/gi, '') || 'lottery'
  const suffix = ext === 'csv' ? 'csv' : 'txt'
  return `投注单-${type}-${compactStamp(when)}.${suffix}`
}

export function formatSlipNumbers(lotteryType, numbers) {
  const parsed = normalizeNumbers(lotteryType, numbers)
  if (!parsed.ok) return ''
  const main = parsed.numbers.main.join(' ')
  const special = parsed.numbers.special?.length ? ` + ${parsed.numbers.special.join(' ')}` : ''
  return `${main}${special}`
}

function emptySlip(lotteryType, name) {
  return {
    empty: true,
    lotteryType,
    name,
    exportedAt: '',
    ticketCount: 0,
    betCount: 0,
    unit: SLIP_UNIT_YUAN,
    total: 0,
    rows: [],
    text: BASKET_SLIP_EMPTY,
    csv: `${CSV_HEADER}\n`,
    message: BASKET_SLIP_EMPTY,
    summary: BASKET_SLIP_EMPTY,
  }
}

export function buildBasketSlip(items, lotteryType, options = {}) {
  const profile = basketProfile(lotteryType)
  const name = profile?.name || ''
  const rows = []
  for (const item of itemsForLottery(items, lotteryType)) {
    const numbers = formatSlipNumbers(lotteryType, item?.numbers)
    if (!numbers) continue
    const bets = betCount(lotteryType, item.numbers)
    if (!bets) continue
    rows.push({
      index: rows.length + 1,
      numbers,
      source: sourceLabel(item),
      note: String(item?.note || '').trim(),
      bets,
      stake: bets * SLIP_UNIT_YUAN,
    })
  }
  if (!rows.length) return emptySlip(lotteryType, name)

  const when = asDate(options.now)
  const exportedAt = formatSlipWhen(when)
  const ticketCount = rows.length
  const betTotal = rows.reduce((sum, row) => sum + row.bets, 0)
  const total = betTotal * SLIP_UNIT_YUAN
  const header = [
    `${name}投注单`,
    `导出时间：${exportedAt}`,
    `注数：${betTotal}`,
    `单价：${SLIP_UNIT_YUAN} 元`,
    `合计：${total} 元`,
  ]
  if (ticketCount !== betTotal) header.push(`行数：${ticketCount}`)
  const text = [
    ...header,
    '',
    ...rows.map(lineText),
    '',
    BASKET_SLIP_DISCLAIMER,
  ].join('\n')
  const csv = [
    CSV_HEADER,
    ...rows.map((row) => [row.index, row.numbers, row.source, row.note, row.stake].map(csvCell).join(',')),
  ].join('\n') + '\n'
  const summary = ticketCount === betTotal
    ? `${betTotal} 注 · 单价 ${SLIP_UNIT_YUAN} 元 · 合计 ${total} 元`
    : `${ticketCount} 行 · ${betTotal} 注 · 单价 ${SLIP_UNIT_YUAN} 元 · 合计 ${total} 元`

  return {
    empty: false,
    lotteryType,
    name,
    exportedAt,
    ticketCount,
    betCount: betTotal,
    unit: SLIP_UNIT_YUAN,
    total,
    rows,
    text,
    csv,
    message: '',
    summary,
  }
}

export function slipDownload(slip, kind, date) {
  const ext = kind === 'csv' ? 'csv' : 'txt'
  const filename = slipFilename(slip?.lotteryType, date, ext)
  if (ext === 'csv') {
    return {
      filename,
      mime: 'text/csv;charset=utf-8',
      content: `\uFEFF${slip?.csv || `${CSV_HEADER}\n`}`,
    }
  }
  return {
    filename,
    mime: 'text/plain;charset=utf-8',
    content: slip?.text || '',
  }
}

export function slipPrintHtml(slip) {
  if (!slip || slip.empty) return ''
  const title = `${slip.name || '彩票'}投注单`
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<style>
  @page { margin: 16mm; }
  body { margin: 0; color: #1a1a1a; background: #fff; }
  pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; font-size: 13px; line-height: 1.65; }
  @media print {
    body { background: #fff; color: #1a1a1a; }
  }
</style>
</head>
<body>
<pre>${escapeHtml(slip.text)}</pre>
</body>
</html>`
}
