import assert from 'node:assert/strict'
import test from 'node:test'

import { applyBasketFilter, filterFromBands, matchFilter, previewBasketFilter, ticketMetrics } from './basketFilter.js'

function item(id, lotteryType, main, special = []) {
  return { id, lottery_type: lotteryType, numbers: { main, special } }
}

test('ticketMetrics 双色球按去重主号算，特别号不并进', () => {
  const metrics = ticketMetrics('ssq', {
    main: ['01', '02', '03', '04', '05', '06'],
    special: ['16'],
  })
  assert.deepEqual(metrics, { sum: 21, span: 5, odd: 3, hewei: 1, ac: 0 })

  const duped = ticketMetrics('ssq', {
    main: ['01', '01', '03', '05', '07', '09'],
    special: ['08'],
  })
  assert.equal(duped.sum, 25)
  assert.equal(duped.span, 8)
  assert.equal(duped.odd, 5)
})

test('ticketMetrics 大乐透只看前区', () => {
  const metrics = ticketMetrics('dlt', {
    main: ['05', '12', '18', '27', '35'],
    special: ['03', '09'],
  })
  assert.equal(metrics.sum, 97)
  assert.equal(metrics.span, 30)
  assert.equal(metrics.odd, 3)
  assert.equal(metrics.hewei, 7)
  assert.equal(metrics.ac, 6)
})

test('ticketMetrics 福彩3D 按整注各位，0 偶 9 奇，重复保留', () => {
  const mixed = ticketMetrics('fc3d', { main: ['0', '5', '9'], special: [] })
  assert.deepEqual(mixed, { sum: 14, span: 9, odd: 2, hewei: 4, ac: 1 })

  const repeated = ticketMetrics('fc3d', { main: ['1', '1', '1'] })
  assert.equal(repeated.sum, 3)
  assert.equal(repeated.span, 0)
  assert.equal(repeated.odd, 3)
  assert.equal(repeated.ac, -1)
})

test('ticketMetrics 快乐八按当前号码集合', () => {
  const metrics = ticketMetrics('kl8', { main: ['02', '15', '16', '80'] })
  assert.equal(metrics.sum, 113)
  assert.equal(metrics.span, 78)
  assert.equal(metrics.odd, 1)
  assert.equal(metrics.hewei, 3)
})

test('ticketMetrics 七星彩特别号不进主号', () => {
  const metrics = ticketMetrics('qxc', {
    main: ['1', '2', '3', '4', '5', '6'],
    special: ['9'],
  })
  assert.equal(metrics.sum, 21)
  assert.equal(metrics.odd, 3)
})

test('ticketMetrics 空号或未知彩种算不出', () => {
  assert.equal(ticketMetrics('ssq', { main: [], special: ['01'] }), null)
  assert.equal(ticketMetrics('nope', { main: ['01'] }), null)
})

test('matchFilter 空条件全部通过，边界含两端', () => {
  const metrics = { sum: 21, span: 5, odd: 3, hewei: 1, ac: 0 }
  assert.equal(matchFilter(metrics, {}), true)
  assert.equal(matchFilter(metrics, null), true)
  assert.equal(matchFilter(metrics, { sumMin: '', sumMax: '  ', spanMin: null }), true)
  assert.equal(matchFilter(metrics, { sumMin: 21, sumMax: 21 }), true)
  assert.equal(matchFilter(metrics, { sumMin: 21 }), true)
  assert.equal(matchFilter(metrics, { sumMax: 21 }), true)
  assert.equal(matchFilter(metrics, { sumMin: 22 }), false)
  assert.equal(matchFilter(metrics, { sumMax: 20 }), false)
  assert.equal(matchFilter(metrics, { oddMin: 3, spanMax: 5, heweiMin: 1, heweiMax: 1, acMin: 0, acMax: 0 }), true)
})

test('matchFilter 只填一边时另一边不限制，下限大于上限则不通过', () => {
  const metrics = { sum: 14, span: 9, odd: 2, hewei: 4, ac: 1 }
  assert.equal(matchFilter(metrics, { spanMin: 9 }), true)
  assert.equal(matchFilter(metrics, { spanMax: 9 }), true)
  assert.equal(matchFilter(metrics, { oddMin: 0, oddMax: '' }), true)
  assert.equal(matchFilter(metrics, { sumMin: 'abc' }), true)
  assert.equal(matchFilter(metrics, { sumMin: 30, sumMax: 10 }), false)
  assert.equal(matchFilter(null, { sumMin: 1 }), false)
  assert.equal(matchFilter(null, {}), true)
})

test('previewBasketFilter 按当前彩种计数，空条件不过滤', () => {
  const items = [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['07']),
    item('b', 'ssq', ['02', '04', '06', '08', '10', '12'], ['09']),
    item('c', 'fc3d', ['1', '2', '3']),
  ]
  const open = previewBasketFilter(items, 'ssq', {})
  assert.deepEqual(open.keepIds, ['a', 'b'])
  assert.deepEqual(open.dropIds, [])
  assert.equal(open.keep.length, 2)
  assert.equal(open.drop.length, 0)
  assert.equal(open.summary.total, 2)
  assert.equal(open.summary.keep, 2)
  assert.equal(open.summary.drop, 0)
  assert.equal(open.summary.active, false)
  assert.match(open.summary.text, /全部保留/)

  const filtered = previewBasketFilter(items, 'ssq', { oddMin: 3, oddMax: 3 })
  assert.deepEqual(filtered.keepIds, ['a'])
  assert.deepEqual(filtered.dropIds, ['b'])
  assert.equal(filtered.summary.keep, 1)
  assert.equal(filtered.summary.drop, 1)
  assert.equal(filtered.summary.active, true)
  assert.match(filtered.drop[0].label, /02 04 06 08 10 12/)
  assert.match(filtered.drop[0].label, /09/)
  assert.equal(filtered.keep[0].metrics.odd, 3)
})

test('previewBasketFilter 越界条件剔除当前彩种全部，空篮友好提示', () => {
  const items = [
    item('a', 'fc3d', ['0', '5', '9']),
    item('b', 'fc3d', ['1', '1', '1']),
    item('c', 'ssq', ['01', '02', '03', '04', '05', '06'], ['01']),
  ]
  const dropped = previewBasketFilter(items, 'fc3d', { sumMin: 100, sumMax: 120 })
  assert.deepEqual(dropped.keepIds, [])
  assert.deepEqual(dropped.dropIds, ['a', 'b'])
  assert.equal(dropped.summary.keep, 0)
  assert.equal(dropped.summary.drop, 2)

  const empty = previewBasketFilter([], 'ssq', { sumMin: 1 })
  assert.deepEqual(empty.keepIds, [])
  assert.deepEqual(empty.dropIds, [])
  assert.equal(empty.summary.total, 0)
  assert.match(empty.summary.text, /空/)

  const blank = previewBasketFilter(items, 'dlt', { sumMin: '', spanMax: null })
  assert.equal(blank.summary.total, 0)
  assert.equal(blank.summary.active, false)
})

test('applyBasketFilter 只移出当前彩种不符的注', () => {
  const items = [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['07']),
    item('b', 'ssq', ['02', '04', '06', '08', '10', '12'], ['09']),
    item('c', 'dlt', ['05', '12', '18', '27', '35'], ['03', '09']),
  ]
  const idle = applyBasketFilter(items, 'ssq', {})
  assert.equal(idle.removedCount, 0)
  assert.deepEqual(idle.items.map((row) => row.id), ['a', 'b', 'c'])

  const applied = applyBasketFilter(items, 'ssq', { sumMax: 21 })
  assert.equal(applied.removedCount, 1)
  assert.deepEqual(applied.removed.map((row) => row.id), ['b'])
  assert.deepEqual(applied.items.map((row) => row.id), ['a', 'c'])
})

test('filterFromBands 只填和值跨度奇数的常见带', () => {
  const next = filterFromBands({
    sum: { low: 80, high: 120 },
    span: { low: 18, high: 28 },
    odd: { low: 2, high: 4 },
  })
  assert.deepEqual(next, {
    sumMin: 80,
    sumMax: 120,
    spanMin: 18,
    spanMax: 28,
    oddMin: 2,
    oddMax: 4,
  })
  assert.deepEqual(filterFromBands({}), {})
  assert.deepEqual(filterFromBands(null), {})
})
