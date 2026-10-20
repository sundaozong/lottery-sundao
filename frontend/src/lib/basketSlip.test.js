import assert from 'node:assert/strict'
import test from 'node:test'

import { betCount } from './basket.js'
import {
  BASKET_SLIP_DISCLAIMER,
  BASKET_SLIP_EMPTY,
  SLIP_UNIT_YUAN,
  buildBasketSlip,
  formatSlipNumbers,
  slipDownload,
  slipFilename,
  slipPrintHtml,
} from './basketSlip.js'

const WHEN = new Date(2026, 9, 20, 9, 45)

function ticket(type, numbers, extra = {}) {
  return {
    id: extra.id || `${type}-${numbers.main.join('')}`,
    lottery_type: type,
    numbers,
    source: extra.source || '',
    strategy: extra.strategy || '',
    note: extra.note || '',
    added_at: extra.added_at || '2026-10-20T01:00:00.000Z',
  }
}

test('空篮给出友好说明，不算金额', () => {
  const slip = buildBasketSlip([], 'ssq', { now: WHEN })
  assert.equal(slip.empty, true)
  assert.equal(slip.ticketCount, 0)
  assert.equal(slip.betCount, 0)
  assert.equal(slip.unit, SLIP_UNIT_YUAN)
  assert.equal(slip.total, 0)
  assert.equal(slip.text, BASKET_SLIP_EMPTY)
  assert.match(slip.text, /空/)
  assert.equal(slip.csv, 'index,numbers,source,note,stake\n')
  assert.deepEqual(slip.rows, [])
  assert.equal(slip.message, BASKET_SLIP_EMPTY)
})

test('只导出当前彩种，别的彩种不进单', () => {
  const items = [
    ticket('dlt', { main: ['01', '02', '03', '04', '05'], special: ['01', '02'] }, { id: 'd' }),
    ticket('ssq', { main: ['01', '02', '03', '04', '05', '06'], special: ['07'] }, { id: 's' }),
  ]
  const slip = buildBasketSlip(items, 'qlc', { now: WHEN })
  assert.equal(slip.empty, true)
  assert.equal(slip.text, BASKET_SLIP_EMPTY)
  assert.equal(buildBasketSlip(items, 'ssq', { now: WHEN }).ticketCount, 1)
})

test('双色球和大乐透按站内格式排号，特别号用加号分开', () => {
  const ssq = formatSlipNumbers('ssq', {
    main: ['33', '1', '12', '5', '22', '18'],
    special: ['9'],
  })
  assert.equal(ssq, '01 05 12 18 22 33 + 09')

  const dlt = formatSlipNumbers('dlt', {
    main: ['35', '3', '21', '8', '15'],
    special: ['12', '1'],
  })
  assert.equal(dlt, '03 08 15 21 35 + 01 12')

  const slip = buildBasketSlip([
    ticket('ssq', { main: ['33', '1', '12', '5', '22', '18'], special: ['9'] }, {
      id: 's1',
      source: 'predict',
      strategy: 'hot',
    }),
    ticket('dlt', { main: ['35', '3', '21', '8', '15'], special: ['12', '1'] }, {
      id: 'd1',
      source: 'manual',
      note: '后区看好',
    }),
  ], 'dlt', { now: WHEN })

  assert.equal(slip.name, '大乐透')
  assert.equal(slip.empty, false)
  assert.match(slip.text, /^大乐透投注单\n/)
  assert.match(slip.text, /导出时间：2026-10-20 09:45/)
  assert.match(slip.text, /1 \| 03 08 15 21 35 \+ 01 12 \| 手选 · 后区看好/)
  assert.doesNotMatch(slip.text, /33/)
  assert.match(slip.text, new RegExp(BASKET_SLIP_DISCLAIMER.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
})

test('数字彩按位保留顺序，七星彩特别号仍分开', () => {
  assert.equal(formatSlipNumbers('fc3d', { main: ['9', '0', '1'], special: [] }), '9 0 1')
  assert.equal(formatSlipNumbers('pl3', { main: ['0', '8', '0'], special: [] }), '0 8 0')
  assert.equal(formatSlipNumbers('pl5', { main: ['5', '0', '1', '9', '2'], special: [] }), '5 0 1 9 2')
  assert.equal(
    formatSlipNumbers('qxc', { main: ['3', '1', '4', '0', '9', '2'], special: ['14'] }),
    '3 1 4 0 9 2 + 14',
  )
  assert.equal(
    formatSlipNumbers('qlc', { main: ['30', '2', '11', '7', '19', '4', '25'], special: [] }),
    '02 04 07 11 19 25 30',
  )

  const slip = buildBasketSlip([
    ticket('fc3d', { main: ['9', '0', '1'] }, { id: 'f', source: 'paste' }),
  ], 'fc3d', { now: WHEN })
  assert.match(slip.text, /1 \| 9 0 1 \| 粘贴/)
  assert.doesNotMatch(slip.text, /0 1 9/)
  assert.match(slip.text, /福彩3D投注单/)
})

test('来源和备注可省略，有内容才挂在行尾', () => {
  const slip = buildBasketSlip([
    ticket('ssq', { main: ['1', '2', '3', '4', '5', '6'], special: ['7'] }, { id: 'bare' }),
    ticket('ssq', { main: ['2', '3', '4', '5', '6', '7'], special: ['8'] }, {
      id: 'noted',
      source: 'analysis',
      note: '回声留下',
    }),
  ], 'ssq', { now: WHEN })
  const lines = slip.text.split('\n')
  assert.equal(lines[6], '1 | 01 02 03 04 05 06 + 07')
  assert.equal(lines[7], '2 | 02 03 04 05 06 07 + 08 | 回声 · 回声留下')
  assert.equal(slip.rows[0].source, '')
  assert.equal(slip.rows[1].source, '回声')
  assert.equal(slip.rows[1].note, '回声留下')
})

test('CSV 转义逗号、引号和换行，金额列是每行注金', () => {
  const slip = buildBasketSlip([
    ticket('ssq', { main: ['1', '2', '3', '4', '5', '6'], special: ['7'] }, {
      id: 'comma',
      source: 'manual',
      note: '周末,备用',
    }),
    ticket('ssq', { main: ['2', '3', '4', '5', '6', '7'], special: ['8'] }, {
      id: 'quote',
      source: '朋友,代买',
      note: '他说"加一注"\n第二行',
    }),
  ], 'ssq', { now: WHEN })
  const csv = slip.csv
  assert.equal(csv.split('\n')[0], 'index,numbers,source,note,stake')
  assert.match(csv, /1,01 02 03 04 05 06 \+ 07,手选,"周末,备用",2/)
  assert.match(csv, /2,02 03 04 05 06 07 \+ 08,"朋友,代买","他说""加一注""\n第二行",2/)
  assert.equal(slip.rows[0].stake, 2)
  assert.equal(slip.rows[1].stake, 2)
})

test('单价 2 元，单注相加，快乐八复式按注数计', () => {
  const singles = buildBasketSlip([
    ticket('pl3', { main: ['1', '2', '3'] }, { id: 'a' }),
    ticket('pl3', { main: ['4', '5', '6'] }, { id: 'b' }),
    ticket('pl3', { main: ['7', '8', '9'] }, { id: 'c' }),
  ], 'pl3', { now: WHEN })
  assert.equal(singles.ticketCount, 3)
  assert.equal(singles.betCount, 3)
  assert.equal(singles.unit, 2)
  assert.equal(singles.total, 6)
  assert.equal(singles.rows.every((row) => row.stake === 2), true)
  assert.match(singles.text, /注数：3\n单价：2 元\n合计：6 元/)

  const kl8Main = Array.from({ length: 11 }, (_, index) => String(index + 1))
  const compound = ticket('kl8', { main: kl8Main, special: [] }, { id: 'k', source: 'expand' })
  const small = ticket('kl8', { main: ['2', '80'], special: [] }, { id: 's', source: 'manual' })
  assert.equal(betCount('kl8', compound.numbers), 11)
  const slip = buildBasketSlip([small, compound], 'kl8', { now: WHEN })
  assert.equal(slip.rows[0].numbers, '02 80')
  assert.equal(slip.rows[0].stake, 2)
  assert.equal(slip.rows[1].stake, 22)
  assert.equal(slip.ticketCount, 2)
  assert.equal(slip.betCount, 12)
  assert.equal(slip.total, 24)
  assert.match(slip.text, /注数：12\n单价：2 元\n合计：24 元/)
  assert.match(slip.text, /行数：2/)
  const stakes = slip.csv.trim().split('\n').slice(1).map((line) => Number(line.split(',').at(-1)))
  assert.deepEqual(stakes, [2, 22])
  assert.equal(stakes.reduce((sum, stake) => sum + stake, 0), slip.total)
})

test('保持篮内顺序，不改传入的条目', () => {
  const items = [
    ticket('ssq', { main: ['9', '8', '7', '6', '5', '4'], special: ['1'] }, { id: 'later', added_at: '2026-10-20T08:00:00.000Z' }),
    ticket('ssq', { main: ['1', '2', '3', '4', '5', '6'], special: ['2'] }, { id: 'earlier', added_at: '2026-10-18T08:00:00.000Z' }),
  ]
  const snapshot = JSON.stringify(items)
  const slip = buildBasketSlip(items, 'ssq', { now: WHEN })
  assert.deepEqual(slip.rows.map((row) => row.index), [1, 2])
  assert.match(slip.rows[0].numbers, /^04 05 06 07 08 09/)
  assert.match(slip.rows[1].numbers, /^01 02 03 04 05 06/)
  assert.equal(JSON.stringify(items), snapshot)
})

test('文件名带彩种和本地时间，CSV 带 UTF-8 BOM', () => {
  assert.equal(slipFilename('fc3d', WHEN, 'txt'), '投注单-fc3d-20261020-0945.txt')
  assert.equal(slipFilename('qxc', new Date(2026, 0, 2, 3, 4), 'csv'), '投注单-qxc-20260102-0304.csv')
  const slip = buildBasketSlip([
    ticket('ssq', { main: ['1', '2', '3', '4', '5', '6'], special: ['7'] }, { id: 'one', note: 'a,b' }),
  ], 'ssq', { now: WHEN })
  const txt = slipDownload(slip, 'txt', WHEN)
  const csv = slipDownload(slip, 'csv', WHEN)
  assert.equal(txt.filename, '投注单-ssq-20261020-0945.txt')
  assert.equal(txt.mime, 'text/plain;charset=utf-8')
  assert.equal(txt.content, slip.text)
  assert.equal(csv.filename, '投注单-ssq-20261020-0945.csv')
  assert.equal(csv.mime, 'text/csv;charset=utf-8')
  assert.equal(csv.content.charCodeAt(0), 0xfeff)
  assert.equal(csv.content.slice(1), slip.csv)
})

test('打印页只含投注单正文，并转义备注里的标记', () => {
  const slip = buildBasketSlip([
    ticket('pl5', { main: ['1', '2', '3', '4', '5'] }, { id: 'p', note: '看 <b> & "号"' }),
  ], 'pl5', { now: WHEN })
  const html = slipPrintHtml(slip)
  assert.match(html, /排列五投注单/)
  assert.match(html, /1 \| 1 2 3 4 5 \| 看 &lt;b&gt; &amp; &quot;号&quot;/)
  assert.match(html, /@media print/)
  assert.doesNotMatch(html, /<b>/)
  assert.equal(slipPrintHtml(buildBasketSlip([], 'pl5', { now: WHEN })), '')
})
