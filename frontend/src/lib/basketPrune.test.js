import assert from 'node:assert/strict'
import test from 'node:test'

import { basketProfile } from './basket.js'
import {
  defaultPruneThreshold,
  previewBasketPrune,
  pruneBasket,
} from './basketPrune.js'

function ticket(id, main, special = []) {
  return { id, numbers: { main, special } }
}

test('默认阈值是 max(2, 主号个数-1)', () => {
  assert.equal(defaultPruneThreshold(basketProfile('ssq')), 5)
  assert.equal(defaultPruneThreshold(basketProfile('dlt')), 4)
  assert.equal(defaultPruneThreshold(basketProfile('qlc')), 6)
  assert.equal(defaultPruneThreshold(basketProfile('fc3d')), 2)
  assert.equal(defaultPruneThreshold(basketProfile('pl3')), 2)
  assert.equal(defaultPruneThreshold(basketProfile('pl5')), 4)
  assert.equal(defaultPruneThreshold(basketProfile('qxc')), 5)
  assert.equal(defaultPruneThreshold(basketProfile('kl8')), 9)
  assert.equal(defaultPruneThreshold(null), 2)
})

test('不足 2 注时不修剪', () => {
  const profile = basketProfile('ssq')
  const empty = pruneBasket([], profile, 5)
  assert.deepEqual(empty.keepIds, [])
  assert.deepEqual(empty.removeIds, [])
  assert.deepEqual(empty.pairsOver, [])
  assert.match(empty.summary.text, /2/)

  const one = pruneBasket([
    ticket('only', ['01', '02', '03', '04', '05', '06'], ['07']),
  ], profile, 5)
  assert.deepEqual(one.keepIds, ['only'])
  assert.deepEqual(one.removeIds, [])
  assert.deepEqual(one.pairsOver, [])
  assert.equal(one.summary.keep, 1)
  assert.equal(one.summary.remove, 0)
  assert.match(one.summary.text, /2/)
})

test('乐透按主号集合交集，阈值边界刚好留下或移出', () => {
  const profile = basketProfile('ssq')
  const tickets = [
    ticket('early', ['01', '02', '03', '04', '05', '06'], ['01']),
    ticket('later', ['01', '02', '03', '04', '15', '16'], ['09']),
  ]
  const under = pruneBasket(tickets, profile, 5)
  assert.deepEqual(under.keepIds, ['early', 'later'])
  assert.deepEqual(under.removeIds, [])
  assert.deepEqual(under.pairsOver, [])
  assert.match(under.summary.text, /全部保留/)

  const hit = pruneBasket([
    ticket('early', ['01', '02', '03', '04', '05', '06'], ['01']),
    ticket('later', ['01', '02', '03', '04', '05', '07'], ['09']),
  ], profile, 5)
  assert.deepEqual(hit.keepIds, ['early'])
  assert.deepEqual(hit.removeIds, ['later'])
  assert.equal(hit.pairsOver.length, 1)
  assert.equal(hit.pairsOver[0].overlap, 5)
  assert.equal(hit.pairsOver[0].specialOverlap, 0)
  assert.equal(hit.pairsOver[0].leftId, 'early')
  assert.equal(hit.pairsOver[0].rightId, 'later')
  assert.match(hit.summary.text, /保留 1/)
  assert.match(hit.summary.text, /移出 1/)
})

test('平局优先移出后加入的注，不看 id 大小', () => {
  const profile = basketProfile('ssq')
  const tickets = [
    ticket('z', ['01', '02', '03', '04', '05', '06'], ['01']),
    ticket('a', ['01', '02', '03', '04', '05', '06'], ['16']),
  ]
  const result = pruneBasket(tickets, profile, 6)
  assert.deepEqual(result.keepIds, ['z'])
  assert.deepEqual(result.removeIds, ['a'])
  assert.equal(result.pairsOver[0].overlap, 6)
  assert.equal(result.pairsOver[0].specialOverlap, 0)
})

test('超阈值边更多的注先移出，即使它更早加入', () => {
  const profile = basketProfile('ssq')
  const center = ticket('center', ['01', '02', '03', '04', '05', '06'], ['01'])
  const left = ticket('left', ['01', '02', '03', '04', '05', '16'], ['02'])
  const right = ticket('right', ['02', '03', '04', '05', '06', '17'], ['03'])
  const result = pruneBasket([left, center, right], profile, 5)
  assert.deepEqual(result.keepIds, ['left', 'right'])
  assert.deepEqual(result.removeIds, ['center'])
  assert.equal(result.remove[0].links, 2)
  assert.equal(result.remove[0].maxOverlap, 5)
})

test('两条互不相连的近重复，各自留下更早的那注', () => {
  const profile = basketProfile('ssq')
  const tickets = [
    ticket('a', ['01', '02', '03', '04', '05', '06'], ['01']),
    ticket('b', ['01', '02', '03', '04', '05', '07'], ['02']),
    ticket('c', ['11', '12', '13', '14', '15', '16'], ['03']),
    ticket('d', ['11', '12', '13', '14', '15', '17'], ['04']),
  ]
  const result = pruneBasket(tickets, profile, 5)
  assert.deepEqual(result.keepIds, ['a', 'c'])
  assert.deepEqual(result.removeIds, ['b', 'd'])
  assert.equal(result.pairsOver.length, 2)
  assert.deepEqual(result.pairsOver.map((pair) => [pair.leftId, pair.rightId]), [['a', 'b'], ['c', 'd']])
})

test('三注互相近重复时只留下最早的一注', () => {
  const profile = basketProfile('dlt')
  const same = ['01', '02', '03', '04', '05']
  const tickets = [
    ticket('first', same, ['01', '02']),
    ticket('second', same, ['03', '04']),
    ticket('third', same, ['05', '06']),
  ]
  const result = pruneBasket(tickets, profile, 4)
  assert.deepEqual(result.keepIds, ['first'])
  assert.deepEqual(result.removeIds, ['second', 'third'])
  assert.equal(result.pairsOver.length, 3)
  assert.equal(result.summary.specialPairs, 0)
})

test('数字彩按位计同位相同，错位相同不算', () => {
  const profile = basketProfile('fc3d')
  const shifted = pruneBasket([
    ticket('a', ['1', '2', '3']),
    ticket('b', ['3', '1', '2']),
  ], profile, 2)
  assert.deepEqual(shifted.removeIds, [])
  assert.deepEqual(shifted.pairsOver, [])

  const one = pruneBasket([
    ticket('a', ['1', '2', '3']),
    ticket('b', ['1', '9', '8']),
  ], profile, 2)
  assert.deepEqual(one.keepIds, ['a', 'b'])
  assert.deepEqual(one.removeIds, [])

  const two = pruneBasket([
    ticket('early', ['1', '2', '3']),
    ticket('later', ['1', '9', '3']),
  ], profile, 2)
  assert.deepEqual(two.keepIds, ['early'])
  assert.deepEqual(two.removeIds, ['later'])
  assert.equal(two.pairsOver[0].overlap, 2)
})

test('七星彩特别号不计入按位重合', () => {
  const profile = basketProfile('qxc')
  const kept = pruneBasket([
    ticket('a', ['1', '2', '3', '4', '5', '6'], ['7']),
    ticket('b', ['1', '2', '3', '4', '9', '8'], ['7']),
  ], profile, 5)
  assert.deepEqual(kept.removeIds, [])
  assert.deepEqual(kept.pairsOver, [])

  const removed = pruneBasket([
    ticket('a', ['1', '2', '3', '4', '5', '6'], ['7']),
    ticket('b', ['1', '2', '3', '4', '5', '9'], ['7']),
  ], profile, 5)
  assert.deepEqual(removed.keepIds, ['a'])
  assert.deepEqual(removed.removeIds, ['b'])
  assert.equal(removed.pairsOver[0].overlap, 5)
  assert.equal(removed.pairsOver[0].specialOverlap, 1)
  assert.equal(removed.summary.specialPairs, 1)
  assert.match(removed.summary.text, /特别号/)
  assert.match(removed.summary.text, /参考/)
})

test('大乐透特别号重合只写进摘要，不单独触发修剪', () => {
  const profile = basketProfile('dlt')
  const onlySpecial = pruneBasket([
    ticket('a', ['01', '02', '03', '04', '05'], ['01', '02']),
    ticket('b', ['06', '07', '08', '09', '10'], ['01', '02']),
  ], profile, 4)
  assert.deepEqual(onlySpecial.removeIds, [])
  assert.equal(onlySpecial.summary.specialPairs, 0)

  const withMain = pruneBasket([
    ticket('a', ['01', '02', '03', '04', '05'], ['01', '02']),
    ticket('b', ['01', '02', '03', '04', '15'], ['02', '08']),
  ], profile, 4)
  assert.deepEqual(withMain.removeIds, ['b'])
  assert.equal(withMain.pairsOver[0].overlap, 4)
  assert.equal(withMain.pairsOver[0].specialOverlap, 1)
  assert.match(withMain.summary.text, /特别号/)
})

test('快乐八按集合交集，号码个数不固定', () => {
  const profile = basketProfile('kl8')
  const base = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10']
  const share8 = pruneBasket([
    ticket('a', base),
    ticket('b', ['01', '02', '03', '04', '05', '06', '07', '08', '11', '12']),
  ], profile, null)
  assert.equal(share8.summary.threshold, 9)
  assert.deepEqual(share8.removeIds, [])

  const share9 = pruneBasket([
    ticket('a', base),
    ticket('b', ['01', '02', '03', '04', '05', '06', '07', '08', '09', '12']),
  ], profile, 9)
  assert.deepEqual(share9.keepIds, ['a'])
  assert.deepEqual(share9.removeIds, ['b'])
  assert.equal(share9.pairsOver[0].overlap, 9)
})

test('七乐彩集合重合达到默认阈值才移出', () => {
  const profile = basketProfile('qlc')
  const result = pruneBasket([
    ticket('a', ['01', '02', '03', '04', '05', '06', '07']),
    ticket('b', ['01', '02', '03', '04', '05', '06', '18']),
    ticket('c', ['01', '02', '03', '04', '05', '19', '20']),
  ], profile, null)
  assert.equal(result.summary.threshold, 6)
  assert.deepEqual(result.keepIds, ['a', 'c'])
  assert.deepEqual(result.removeIds, ['b'])
  assert.equal(result.pairsOver.length, 1)
  assert.equal(result.pairsOver[0].overlap, 6)
})

test('阈值高于主号个数时，完全相同的注也保留', () => {
  const profile = basketProfile('pl5')
  const tickets = [
    ticket('a', ['1', '2', '3', '4', '5']),
    ticket('b', ['1', '2', '3', '4', '5']),
  ]
  const same = pruneBasket(tickets, profile, 5)
  assert.deepEqual(same.removeIds, ['b'])
  const above = pruneBasket(tickets, profile, 6)
  assert.deepEqual(above.keepIds, ['a', 'b'])
  assert.deepEqual(above.removeIds, [])
})

test('空阈值、非法阈值回退到默认', () => {
  const profile = basketProfile('ssq')
  const tickets = [
    ticket('a', ['01', '02', '03', '04', '05', '06'], ['01']),
    ticket('b', ['01', '02', '03', '04', '05', '07'], ['02']),
  ]
  for (const threshold of [null, '', '  ', 'nope', 0, -3, 1.5]) {
    const result = pruneBasket(tickets, profile, threshold)
    assert.equal(result.summary.threshold, 5, String(threshold))
    assert.deepEqual(result.removeIds, ['b'])
  }
})

test('只修剪当前彩种，未知彩种不编造结果', () => {
  const items = [
    { id: 's1', lottery_type: 'ssq', numbers: { main: ['01', '02', '03', '04', '05', '06'], special: ['01'] } },
    { id: 's2', lottery_type: 'ssq', numbers: { main: ['01', '02', '03', '04', '05', '07'], special: ['02'] } },
    { id: 'd1', lottery_type: 'dlt', numbers: { main: ['01', '02', '03', '04', '05'], special: ['01', '02'] } },
  ]
  const ssq = previewBasketPrune(items, 'ssq', 5)
  assert.deepEqual(ssq.keepIds, ['s1'])
  assert.deepEqual(ssq.removeIds, ['s2'])
  assert.equal(ssq.remove[0].label.includes('01'), true)

  const dlt = previewBasketPrune(items, 'dlt', 4)
  assert.deepEqual(dlt.keepIds, ['d1'])
  assert.deepEqual(dlt.removeIds, [])
  assert.match(dlt.summary.text, /2/)

  const unknown = previewBasketPrune(items, 'nope', 2)
  assert.deepEqual(unknown.keepIds, [])
  assert.deepEqual(unknown.removeIds, [])
  assert.equal(unknown.summary.text, '未知彩种')
})

test('结果稳定且不改入参', () => {
  const profile = basketProfile('fc3d')
  const tickets = [
    ticket('a', ['1', '2', '3']),
    ticket('b', ['1', '2', '9']),
    ticket('c', ['8', '7', '6']),
  ]
  const snapshot = JSON.parse(JSON.stringify(tickets))
  const first = pruneBasket(tickets, profile, 2)
  const second = pruneBasket(tickets, profile, 2)
  assert.deepEqual(first, second)
  assert.deepEqual(tickets, snapshot)
  assert.deepEqual(first.keepIds, ['a', 'c'])
  assert.deepEqual(first.removeIds, ['b'])
})
