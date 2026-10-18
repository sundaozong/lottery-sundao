import assert from 'node:assert/strict'
import test from 'node:test'

import { addToBasket } from './basket.js'
import {
  emptyTrendDraft,
  isTrendPicked,
  omitHeatLevel,
  omitHeatMax,
  removeTrendAt,
  toggleTrendNumber,
  trendDraftState,
} from './trendPick.js'

const NOW = '2026-10-18T12:00:00.000Z'

function pick(type, draft, zone, number) {
  return toggleTrendNumber(type, draft, zone, number)
}

test('双色球点选补零、排序，再点一次取消', () => {
  let draft = emptyTrendDraft()
  let step = pick('ssq', draft, 'main', 16)
  assert.equal(step.status, 'added')
  step = pick('ssq', step.draft, 'main', '1')
  step = pick('ssq', step.draft, 'main', 8)
  assert.deepEqual(step.draft.main, ['01', '08', '16'])
  assert.equal(isTrendPicked('ssq', step.draft, 'main', '08'), true)
  assert.equal(isTrendPicked('ssq', step.draft, 'main', 2), false)

  step = pick('ssq', step.draft, 'main', '08')
  assert.equal(step.status, 'removed')
  assert.deepEqual(step.draft.main, ['01', '16'])
})

test('双色球主号满 6 个后不再追加，蓝球点另一个会换掉', () => {
  let draft = emptyTrendDraft()
  for (const n of [1, 2, 3, 4, 5, 6]) draft = pick('ssq', draft, 'main', n).draft
  const full = pick('ssq', draft, 'main', 7)
  assert.equal(full.status, 'full')
  assert.match(full.message, /已满/)
  assert.deepEqual(full.draft.main, ['01', '02', '03', '04', '05', '06'])

  let blue = pick('ssq', full.draft, 'special', 7)
  assert.deepEqual(blue.draft.special, ['07'])
  blue = pick('ssq', blue.draft, 'special', 16)
  assert.equal(blue.status, 'added')
  assert.deepEqual(blue.draft.special, ['16'])
  blue = pick('ssq', blue.draft, 'special', 16)
  assert.equal(blue.status, 'removed')
  assert.deepEqual(blue.draft.special, [])
})

test('大乐透后区满 2 个就停，个数不够时说明还差什么', () => {
  let draft = emptyTrendDraft()
  for (const n of [5, 11, 19, 28, 33]) draft = pick('dlt', draft, 'main', n).draft
  draft = pick('dlt', draft, 'special', 2).draft
  draft = pick('dlt', draft, 'special', 10).draft
  const extra = pick('dlt', draft, 'special', 11)
  assert.equal(extra.status, 'full')
  assert.deepEqual(extra.draft.special, ['02', '10'])

  const partial = trendDraftState('dlt', { main: ['05', '11', '19', '28', '33'], special: ['02'] })
  assert.equal(partial.complete, false)
  assert.match(partial.message, /后区/)
  assert.match(partial.message, /1/)

  const ready = trendDraftState('dlt', extra.draft)
  assert.equal(ready.complete, true)
  assert.deepEqual(ready.numbers.special, ['02', '10'])
})

test('数字彩按点击顺序排位，未满可以重复，满了再点已选号去掉最后一次', () => {
  let draft = emptyTrendDraft()
  draft = pick('fc3d', draft, 'main', 1).draft
  draft = pick('fc3d', draft, 'main', 1).draft
  draft = pick('fc3d', draft, 'main', 2).draft
  assert.deepEqual(draft.main, ['1', '1', '2'])
  assert.equal(trendDraftState('fc3d', draft).complete, true)

  const blocked = pick('fc3d', draft, 'main', 9)
  assert.equal(blocked.status, 'full')
  assert.deepEqual(blocked.draft.main, ['1', '1', '2'])

  const dropped = pick('fc3d', draft, 'main', 1)
  assert.equal(dropped.status, 'removed')
  assert.deepEqual(dropped.draft.main, ['1', '2'])

  const early = trendDraftState('pl5', { main: ['1', '2', '3'], special: [] })
  assert.equal(early.complete, false)
  assert.match(early.message, /2/)

  let qxc = emptyTrendDraft()
  for (const n of [1, 2, 3, 4, 5, 6]) qxc = pick('qxc', qxc, 'main', n).draft
  assert.match(trendDraftState('qxc', qxc).message, /特别号/)
  qxc = pick('qxc', qxc, 'special', 14).draft
  const qxcState = trendDraftState('qxc', qxc)
  assert.equal(qxcState.complete, true)
  assert.deepEqual(qxcState.numbers.main, ['1', '2', '3', '4', '5', '6'])
  assert.deepEqual(qxcState.numbers.special, ['14'])
})

test('七乐彩特别号并进基本号，快乐八手选最多 10 个', () => {
  let qlc = pick('qlc', emptyTrendDraft(), 'special', 9)
  assert.deepEqual(qlc.draft.main, ['09'])
  assert.deepEqual(qlc.draft.special, [])
  assert.equal(isTrendPicked('qlc', qlc.draft, 'special', 9), true)
  assert.equal(isTrendPicked('qlc', qlc.draft, 'main', '09'), true)
  qlc = pick('qlc', qlc.draft, 'main', 9)
  assert.equal(qlc.status, 'removed')
  assert.deepEqual(qlc.draft.main, [])

  let kl8 = emptyTrendDraft()
  for (let n = 1; n <= 10; n += 1) kl8 = pick('kl8', kl8, 'main', n).draft
  const overflow = pick('kl8', kl8, 'main', 11)
  assert.equal(overflow.status, 'full')
  assert.equal(overflow.draft.main.length, 10)
  assert.equal(trendDraftState('kl8', { main: ['01'], special: [] }).complete, true)
  assert.equal(trendDraftState('kl8', emptyTrendDraft()).complete, false)
})

test('号码超出范围或彩种不明时不改草稿', () => {
  const draft = { main: ['01'], special: [] }
  const range = pick('ssq', draft, 'main', 34)
  assert.equal(range.status, 'invalid')
  assert.deepEqual(range.draft, draft)
  const unknown = pick('nope', draft, 'main', 1)
  assert.equal(unknown.status, 'invalid')
  assert.match(unknown.message, /彩种/)
})

test('草稿球可以按位置移出，选满的一注能放进选号篮', () => {
  const trimmed = removeTrendAt({ main: ['3', '1', '2'], special: [] }, 'main', 1)
  assert.deepEqual(trimmed.main, ['3', '2'])

  let draft = emptyTrendDraft()
  for (const n of [33, 1, 8, 9, 16, 23]) draft = pick('ssq', draft, 'main', n).draft
  draft = pick('ssq', draft, 'special', 7).draft
  const state = trendDraftState('ssq', draft)
  assert.equal(state.complete, true)
  const added = addToBasket([], {
    lottery_type: 'ssq',
    numbers: state.numbers,
    source: 'manual',
    note: '走势点选',
  }, { now: NOW, id: 'trend' })
  assert.equal(added.status, 'added')
  assert.deepEqual(added.item.numbers.main, ['01', '08', '09', '16', '23', '33'])
  assert.deepEqual(added.item.numbers.special, ['07'])
  assert.equal(added.item.note, '走势点选')
})

test('遗漏热力按当前窗口最大值分档，0 和无效值保持最淡', () => {
  assert.equal(omitHeatLevel(0, 9), 0)
  assert.equal(omitHeatLevel(3, 9), 1)
  assert.equal(omitHeatLevel(6, 9), 2)
  assert.equal(omitHeatLevel(7, 9), 3)
  assert.equal(omitHeatLevel(9, 9), 3)
  assert.equal(omitHeatLevel('nope', 9), 0)
  assert.equal(omitHeatLevel(4, 0), 0)

  const max = omitHeatMax([
    { mainOmit: { '01': 1, '02': 4 } },
    { mainOmit: { '01': 0, '02': 9 } },
    { specialOmit: { '01': 20 } },
  ], 'mainOmit')
  assert.equal(max, 9)
  assert.equal(omitHeatMax([], 'mainOmit'), 0)
})
