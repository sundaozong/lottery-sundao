import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildFormRank,
  defaultMinCentered,
  formRankRemovalIds,
  formRankRemovalPreview,
  isSkewed,
  parseMinCentered,
  rankFormRows,
  reportsFromBatch,
  scoreBasketTickets,
  scoreFormReport,
} from './basketFormRank.js'

function report(centered, low, high, unavailable = 0, extra = {}) {
  return {
    summary: { centered, low, high, unavailable },
    glance: extra.glance || `${centered} 项居中`,
    special_metrics: extra.special_metrics || [],
    metrics: extra.metrics || [],
  }
}

function row(id, centered, low, high, addedAt, extra = {}) {
  return {
    id,
    addedAt,
    label: extra.label || id,
    report: extra.error ? null : report(centered, low, high, extra.unavailable || 0, extra),
    error: extra.error || '',
  }
}

test('分数只用主号居中项，特别号只作备注', () => {
  const plain = scoreFormReport(report(3, 2, 1, 2))
  const withSpecial = scoreFormReport(report(3, 2, 1, 2, {
    special_metrics: [
      { stance: 'center' },
      { stance: 'center' },
      { stance: 'low' },
      { stance: 'unavailable' },
    ],
  }))
  assert.equal(plain.score, 3)
  assert.equal(plain.low, 2)
  assert.equal(plain.high, 1)
  assert.equal(plain.skew, 3)
  assert.equal(plain.available, 6)
  assert.equal(plain.specialNote, '')
  assert.equal(withSpecial.score, plain.score)
  assert.equal(withSpecial.skew, plain.skew)
  assert.equal(withSpecial.specialNote, '特别号 2 居中 · 1 偏低 · 1 暂无')
})

test('样本不足沿用一注体检文案，不记成偏态', () => {
  const short = scoreFormReport(report(0, 0, 0, 8, { glance: '还没有历史可对照' }))
  const blank = scoreFormReport(report(0, 0, 0, 8, { glance: '这注形态算不出来' }))
  assert.equal(short.sampleShort, true)
  assert.equal(short.ok, true)
  assert.equal(short.score, 0)
  assert.equal(isSkewed(short, null), false)
  assert.equal(isSkewed(blank, 4), false)
  assert.equal(defaultMinCentered(0), 0)
})

test('默认阈值是可用项一半，低于才算偏态', () => {
  assert.equal(defaultMinCentered(8), 4)
  assert.equal(defaultMinCentered(7), 4)
  assert.equal(defaultMinCentered(1), 1)
  const eight = scoreFormReport(report(4, 2, 2, 0))
  const seven = scoreFormReport(report(3, 2, 2, 0))
  const edge = scoreFormReport(report(4, 3, 0, 0))
  assert.equal(eight.available, 8)
  assert.equal(isSkewed(eight, null), false)
  assert.equal(isSkewed(seven, null), true)
  assert.equal(seven.available, 7)
  assert.equal(isSkewed(edge, null), false)
  assert.equal(isSkewed(scoreFormReport(report(0, 1, 0, 0)), null), true)
  assert.equal(isSkewed(scoreFormReport(report(5, 1, 2, 0)), 6), true)
  assert.equal(isSkewed(scoreFormReport(report(6, 1, 1, 0)), 6), false)
})

test('最低居中项数留空用默认，非法值不通过', () => {
  assert.deepEqual(parseMinCentered(''), { ok: true, value: null, message: '' })
  assert.deepEqual(parseMinCentered('  '), { ok: true, value: null, message: '' })
  assert.deepEqual(parseMinCentered(null), { ok: true, value: null, message: '' })
  assert.equal(parseMinCentered('4').value, 4)
  assert.equal(parseMinCentered(0).value, 0)
  assert.equal(parseMinCentered('8').ok, true)
  assert.equal(parseMinCentered('-1').ok, false)
  assert.equal(parseMinCentered('1.5').ok, false)
  assert.equal(parseMinCentered('9').ok, false)
  assert.equal(parseMinCentered('abc').ok, false)
  assert.match(parseMinCentered('9').message, /0 到 8/)
})

test('空篮和单注都有明确结果', () => {
  const empty = buildFormRank([], 'ssq', {})
  assert.deepEqual(empty.rows, [])
  assert.deepEqual(empty.skewedIds, [])
  assert.match(empty.summary.text, /空的/)

  const one = buildFormRank([
    { id: 'only', lottery_type: 'ssq', added_at: '2024-01-01T00:00:00.000Z', numbers: { main: ['01'], special: [] } },
  ], 'ssq', {
    only: report(2, 4, 2, 0),
  })
  assert.equal(one.summary.total, 1)
  assert.equal(one.rows.length, 1)
  assert.equal(one.rows[0].id, 'only')
  assert.equal(one.rows[0].scored.score, 2)
  assert.deepEqual(one.skewedIds, ['only'])
  assert.equal(one.rows[0].badge.text, '偏态')
})

test('只给当前彩种打分，其他彩种不进名单', () => {
  const ranked = buildFormRank([
    { id: 'ssq-1', lottery_type: 'ssq', added_at: '2024-01-02T00:00:00.000Z', numbers: { main: ['01'], special: [] } },
    { id: 'dlt-1', lottery_type: 'dlt', added_at: '2024-01-01T00:00:00.000Z', numbers: { main: ['02'], special: [] } },
  ], 'ssq', {
    'ssq-1': report(8, 0, 0, 0, { glance: '形态居中' }),
    'dlt-1': report(0, 8, 0, 0),
  })
  assert.deepEqual(ranked.rows.map((item) => item.id), ['ssq-1'])
  assert.deepEqual(ranked.skewedIds, [])
  assert.equal(ranked.rows[0].badge.text, '居中')
})

test('并列时偏态更少优先，再按加入时间，且不改原数组', () => {
  const rows = [
    row('late-skew', 5, 2, 1, '2024-05-01T00:00:00.000Z'),
    row('early-clean', 5, 0, 1, '2024-01-01T00:00:00.000Z'),
    row('top', 6, 2, 0, '2024-06-01T00:00:00.000Z'),
    row('late-clean', 5, 1, 0, '2024-03-01T00:00:00.000Z'),
  ]
  const snapshot = rows.map((item) => item.id)
  const desc = rankFormRows(rows, 'desc')
  assert.deepEqual(desc.map((item) => item.id), ['top', 'early-clean', 'late-clean', 'late-skew'])
  const asc = rankFormRows(rows, 'asc')
  assert.deepEqual(asc.map((item) => item.id), ['early-clean', 'late-clean', 'late-skew', 'top'])
  assert.deepEqual(rows.map((item) => item.id), snapshot)
})

test('分数和偏态都相同的注保持加入顺序', () => {
  const rows = [
    row('second', 4, 1, 1, '2024-02-01T00:00:00.000Z'),
    row('first', 4, 1, 1, '2024-01-01T00:00:00.000Z'),
    row('same-time-b', 4, 1, 1, '2024-03-01T00:00:00.000Z'),
    row('same-time-a', 4, 1, 1, '2024-03-01T00:00:00.000Z'),
  ]
  const ranked = rankFormRows(rows, 'desc')
  assert.deepEqual(ranked.map((item) => item.id), ['first', 'second', 'same-time-b', 'same-time-a'])
})

test('某一注失败不影响其他注的排序', () => {
  const rows = [
    row('ok-low', 2, 3, 3, '2024-01-01T00:00:00.000Z'),
    row('bad', 0, 0, 0, '2024-01-03T00:00:00.000Z', { error: '号码超出范围' }),
    row('ok-high', 7, 1, 0, '2024-01-02T00:00:00.000Z'),
  ]
  const desc = rankFormRows(rows, 'desc')
  assert.deepEqual(desc.map((item) => item.id), ['ok-high', 'ok-low', 'bad'])
  assert.equal(desc[2].scored.ok, false)
  assert.equal(desc[2].scored.error, '号码超出范围')
  const asc = rankFormRows(rows, 'asc')
  assert.deepEqual(asc.map((item) => item.id), ['ok-low', 'ok-high', 'bad'])
})

test('非法阈值不勾偏态，合法阈值按最低居中项勾选', () => {
  const items = [
    { id: 'low', lottery_type: 'ssq', added_at: '2024-01-01T00:00:00.000Z', numbers: { main: ['01', '02'], special: [] } },
    { id: 'mid', lottery_type: 'ssq', added_at: '2024-01-02T00:00:00.000Z', numbers: { main: ['03', '04'], special: ['05'] } },
    { id: 'high', lottery_type: 'ssq', added_at: '2024-01-03T00:00:00.000Z', numbers: { main: ['06'], special: [] } },
  ]
  const reports = {
    low: report(2, 3, 3, 0),
    mid: report(4, 2, 2, 0),
    high: report(7, 1, 0, 0, { glance: '形态居中' }),
  }
  const invalid = buildFormRank(items, 'ssq', reports, { minCentered: '9' })
  assert.equal(invalid.threshold.ok, false)
  assert.deepEqual(invalid.skewedIds, [])
  assert.match(invalid.summary.text, /无效/)

  const custom = buildFormRank(items, 'ssq', reports, { minCentered: '5' })
  assert.deepEqual(custom.skewedIds, ['low', 'mid'])
  assert.match(custom.summary.text, /少于 5/)
  assert.equal(custom.rows[0].id, 'high')
  assert.equal(custom.rows[0].label, '06')
  assert.equal(custom.rows.find((item) => item.id === 'mid').label, '03 04 + 05')
})

test('移出名单只含当前彩种里勾中的注，忽略未知 id', () => {
  const items = [
    { id: 'keep', lottery_type: 'ssq' },
    { id: 'drop-b', lottery_type: 'ssq' },
    { id: 'other', lottery_type: 'dlt' },
    { id: 'drop-a', lottery_type: 'ssq' },
    null,
    { id: 'drop-b', lottery_type: 'ssq' },
  ]
  assert.deepEqual(formRankRemovalIds(items, 'ssq', ['missing', 'drop-b', 'other', 'drop-a']), ['drop-b', 'drop-a'])
  assert.deepEqual(formRankRemovalIds(items, 'ssq', []), [])
  assert.deepEqual(formRankRemovalIds([], 'ssq', ['drop-a']), [])
})

test('移出预览按面板顺序给出数量和名单', () => {
  const rows = [
    { id: 'a', label: '01 02' },
    { id: 'b', label: '03 04' },
    { id: 'c', label: '05 06' },
    { id: 'd', label: '07 08' },
  ]
  const preview = formRankRemovalPreview(rows, ['c', 'a', 'missing'], 2)
  assert.deepEqual(preview.ids, ['a', 'c'])
  assert.equal(preview.count, 2)
  assert.deepEqual(preview.shown, ['01 02', '05 06'])
  assert.equal(preview.hidden, 0)
  assert.match(preview.text, /2 注/)
  assert.match(preview.text, /01 02/)

  const long = formRankRemovalPreview(rows, ['a', 'b', 'c', 'd'], 2)
  assert.equal(long.hidden, 2)
  assert.match(long.text, /还有 2/)
  const none = formRankRemovalPreview(rows, [])
  assert.equal(none.count, 0)
  assert.match(none.text, /没有勾选/)
})

test('批量结果缺行或单注失败时，只标那一注', () => {
  const map = reportsFromBatch(['a', 'b', 'c'], {
    items: [
      { id: 'a', ok: true, report: report(6, 1, 1, 0) },
      { id: 'b', ok: false, error: '号码超出范围', report: null },
    ],
  })
  assert.equal(map.a.report.summary.centered, 6)
  assert.equal(map.b.error, '号码超出范围')
  assert.equal(map.c.error, '没有返回这注')
})

test('分块请求失败不影响其他块', async () => {
  const tickets = [
    { id: 'a', main: ['01'] },
    { id: 'b', main: ['02'] },
    { id: 'c', main: ['03'] },
  ]
  let calls = 0
  const reports = await scoreBasketTickets(tickets, async ({ tickets: chunk, limit }) => {
    calls += 1
    assert.equal(limit, 80)
    if (chunk.some((item) => item.id === 'c')) throw new Error('超时')
    return {
      items: chunk.map((item) => ({
        id: item.id,
        ok: item.id !== 'b',
        error: item.id === 'b' ? '号码超出范围' : '',
        report: item.id === 'b' ? null : report(6, 1, 1, 0),
      })),
    }
  }, { chunkSize: 2, limit: 80 })
  assert.equal(calls, 2)
  assert.equal(reports.a.report.summary.centered, 6)
  assert.equal(reports.b.error, '号码超出范围')
  assert.equal(reports.c.error, '超时')
})
