import assert from 'node:assert/strict'
import test from 'node:test'

import {
  BASKET_STORAGE_KEY,
  addManyToBasket,
  addToBasket,
  basketCollision,
  clearBasket,
  clearLottery,
  formatBasketText,
  itemsForLottery,
  lineCost,
  loadBasket,
  recordBody,
  removeFromBasket,
  saveBasket,
  writeBasketRecords,
} from './basket.js'

const NOW = '2026-10-18T12:00:00.000Z'

function memoryStorage(initial = {}) {
  const data = { ...initial }
  return {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null
    },
    setItem(key, value) {
      data[key] = String(value)
    },
  }
}

function ssq(main, special = ['07']) {
  return { main, special }
}

test('同彩种同号码只保留一注，顺序和补零不影响', () => {
  const first = addToBasket([], {
    lottery_type: 'ssq',
    numbers: ssq(['1', '8', '9', '16', '23', '33'], ['7']),
    source: 'predict',
    strategy: 'hot',
  }, { now: NOW, id: 'a' })
  assert.equal(first.status, 'added')
  assert.deepEqual(first.item.numbers.main, ['01', '08', '09', '16', '23', '33'])
  assert.deepEqual(first.item.numbers.special, ['07'])
  assert.equal(first.item.source, 'predict')
  assert.equal(first.item.strategy, 'hot')
  assert.equal(first.item.added_at, NOW)

  const second = addToBasket(first.items, {
    lottery_type: 'ssq',
    numbers: ssq(['33', '01', '08', '09', '16', '23'], ['07']),
    source: 'manual',
  }, { now: NOW, id: 'b' })
  assert.equal(second.status, 'duplicate')
  assert.equal(second.items.length, 1)
  assert.match(second.message, /已在选号篮/)
})

test('不同彩种或不同特别号可以同时在篮里', () => {
  let items = []
  items = addToBasket(items, {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']),
  }, { now: NOW, id: 'ssq' }).items
  items = addToBasket(items, {
    lottery_type: 'dlt',
    numbers: { main: ['01', '02', '03', '04', '05'], special: ['01', '02'] },
  }, { now: NOW, id: 'dlt' }).items
  const otherBlue = addToBasket(items, {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05', '06'], ['08']),
  }, { now: NOW, id: 'blue' })
  assert.equal(otherBlue.status, 'added')
  assert.deepEqual(itemsForLottery(otherBlue.items, 'ssq').map((item) => item.id), ['ssq', 'blue'])
  assert.equal(itemsForLottery(otherBlue.items, 'dlt').length, 1)
})

test('数字彩按位置区分，相同数字换位不算重复', () => {
  const first = addToBasket([], {
    lottery_type: 'fc3d',
    numbers: { main: ['1', '2', '3'], special: [] },
  }, { now: NOW, id: 'p1' })
  const second = addToBasket(first.items, {
    lottery_type: 'fc3d',
    numbers: { main: ['3', '2', '1'] },
  }, { now: NOW, id: 'p2' })
  assert.equal(second.status, 'added')
  assert.deepEqual(second.items[1].numbers.main, ['3', '2', '1'])
})

test('号码个数或范围不对时拒绝加入', () => {
  const short = addToBasket([], {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05'], ['07']),
  }, { now: NOW, id: 'bad' })
  assert.equal(short.status, 'invalid')
  assert.equal(short.items.length, 0)
  assert.match(short.message, /6/)

  const range = addToBasket([], {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05', '34'], ['07']),
  })
  assert.equal(range.status, 'invalid')
})

test('批量加入统计新注和重复注', () => {
  const existing = addToBasket([], {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']),
  }, { now: NOW, id: 'old' }).items
  const result = addManyToBasket(existing, [
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']), source: 'predict' },
    { lottery_type: 'ssq', numbers: ssq(['02', '03', '04', '05', '06', '07'], ['08']), source: 'predict', strategy: 'cold' },
    { lottery_type: 'ssq', numbers: ssq(['1'], ['1']), source: 'predict' },
  ], { now: NOW, ids: ['dup', 'new', 'bad'] })
  assert.equal(result.added, 1)
  assert.equal(result.duplicates, 1)
  assert.equal(result.invalid.length, 1)
  assert.equal(result.items.length, 2)
  assert.equal(result.items[1].id, 'new')
  assert.equal(result.items[1].strategy, 'cold')
})

test('删除、清空本彩种和清空全部互不影响其他彩种', () => {
  let items = addManyToBasket([], [
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']) },
    { lottery_type: 'ssq', numbers: ssq(['02', '03', '04', '05', '06', '07'], ['08']) },
    { lottery_type: 'pl3', numbers: { main: ['1', '2', '3'] } },
  ], { now: NOW, ids: ['s1', 's2', 'p1'] }).items
  items = removeFromBasket(items, 's1')
  assert.deepEqual(items.map((item) => item.id), ['s2', 'p1'])
  items = removeFromBasket(items, 'missing')
  assert.equal(items.length, 2)
  items = clearLottery(items, 'ssq')
  assert.deepEqual(items.map((item) => item.id), ['p1'])
  assert.deepEqual(clearBasket(), [])
})

test('localStorage 往返，损坏数据当成空篮', () => {
  const saved = addToBasket([], {
    lottery_type: 'qxc',
    numbers: { main: ['1', '2', '3', '4', '5', '6'], special: ['7'] },
    source: 'analysis',
    note: '回声对照',
  }, { now: NOW, id: 'q1' }).items
  const storage = memoryStorage()
  saveBasket(storage, saved)
  const loaded = loadBasket(storage)
  assert.equal(loaded.length, 1)
  assert.equal(loaded[0].note, '回声对照')
  assert.equal(loaded[0].lottery_type, 'qxc')
  assert.equal(storage.getItem(BASKET_STORAGE_KEY) != null, true)

  const broken = memoryStorage({ [BASKET_STORAGE_KEY]: '{oops' })
  assert.deepEqual(loadBasket(broken), [])
  const junk = memoryStorage({ [BASKET_STORAGE_KEY]: JSON.stringify([{ id: 'x' }, { lottery_type: 'nope', numbers: { main: ['1'] } }]) })
  assert.deepEqual(loadBasket(junk), [])
})

test('乐透撞号标出重复主号，并列出没覆盖到的号', () => {
  const items = addManyToBasket([], [
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']) },
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '10', '11', '12'], ['16']) },
  ], { now: NOW, ids: ['a', 'b'] }).items
  const report = basketCollision('ssq', items)
  assert.equal(report.ticketCount, 2)
  assert.deepEqual(report.repeatedMain.map((hit) => hit.n), ['01', '02', '03'])
  assert.equal(report.repeatedSpecial.length, 0)
  assert.equal(report.holes.includes('01'), false)
  assert.equal(report.holes.includes('13'), true)
  assert.equal(report.holes.length <= 24, true)
  assert.match(report.summary, /重复/)
  assert.match(report.disclaimer, /不构成投注建议/)
  assert.equal(report.pairs[0].overlapCount, 3)
})

test('数字彩只把同位相同算成撞号', () => {
  const items = addManyToBasket([], [
    { lottery_type: 'fc3d', numbers: { main: ['1', '2', '3'] } },
    { lottery_type: 'fc3d', numbers: { main: ['1', '9', '3'] } },
  ], { now: NOW, ids: ['a', 'b'] }).items
  const report = basketCollision('fc3d', items)
  assert.equal(report.mode, 'digit')
  assert.deepEqual(report.repeatedMain.map((hit) => hit.position), [0, 2])
  assert.deepEqual(report.holes, [])
  assert.match(report.summary, /同位|重复/)
})

test('不足两注时只给提示，不编造撞号', () => {
  const items = addToBasket([], {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']),
  }, { now: NOW, id: 'only' }).items
  const report = basketCollision('ssq', items)
  assert.equal(report.ticketCount, 1)
  assert.deepEqual(report.repeatedMain, [])
  assert.match(report.summary, /2/)
})

test('撞号只看当前彩种', () => {
  const items = addManyToBasket([], [
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']) },
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '04', '05', '16'], ['08']) },
    { lottery_type: 'dlt', numbers: { main: ['01', '02', '03', '04', '05'], special: ['01', '02'] } },
  ], { now: NOW, ids: ['a', 'b', 'c'] }).items
  const report = basketCollision('dlt', items)
  assert.equal(report.ticketCount, 1)
})

test('复制文本带号码和免责声明', () => {
  const items = addToBasket([], {
    lottery_type: 'dlt',
    numbers: { main: ['5', '11', '19', '28', '33'], special: ['2', '10'] },
  }, { now: NOW, id: 'd' }).items
  const text = formatBasketText(items, 'dlt')
  assert.match(text, /大乐透/)
  assert.match(text, /05 11 19 28 33 \+ 02 10/)
  assert.match(text, /不构成投注建议/)
  assert.equal(formatBasketText(items, 'ssq'), '')
})

test('写入购彩记录使用单注金额乘倍数，失败的留下', async () => {
  const items = addManyToBasket([], [
    { lottery_type: 'ssq', numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']), source: 'predict', strategy: 'hot' },
    { lottery_type: 'ssq', numbers: ssq(['02', '03', '04', '05', '06', '07'], ['08']), source: 'predict', strategy: 'hot' },
  ], { now: NOW, ids: ['ok', 'bad'] }).items
  const calls = []
  const result = await writeBasketRecords(items, async (body) => {
    calls.push(body)
    if (body.numbers.main[0] === '02') throw new Error('拒了')
    return { id: 9 }
  }, { issue: '待定', multiple: 2, today: '2026-10-18' })
  assert.deepEqual(result.createdIds, ['ok'])
  assert.equal(result.errors.length, 1)
  assert.equal(result.errors[0].message, '拒了')
  assert.equal(calls[0].lottery_type, 'ssq')
  assert.equal(calls[0].issue, '待定')
  assert.equal(calls[0].cost, 4)
  assert.equal(calls[0].prize, 0)
  assert.equal(calls[0].purchased_at, '2026-10-18')
  assert.equal(calls[0].numbers.play, 'single')
  assert.equal(calls[0].numbers.multiple, 2)
  assert.match(calls[0].note, /预测/)
  assert.match(calls[0].note, /热号/)
})

test('福彩3D 和七星彩按位写入，快乐八二十个号按选十复式计费', () => {
  const fc3d = addToBasket([], {
    lottery_type: 'fc3d',
    numbers: { main: ['1', '2', '3'] },
    source: 'manual',
  }, { now: NOW, id: 'f' }).item
  const body = recordBody(fc3d, { issue: '', multiple: 1, today: '2026-10-18' })
  assert.equal(body.issue, '')
  assert.equal(body.cost, 2)
  assert.equal(body.numbers.play, 'direct')
  assert.deepEqual(body.numbers.positions, [['1'], ['2'], ['3']])

  const qxc = addToBasket([], {
    lottery_type: 'qxc',
    numbers: { main: ['0', '1', '2', '3', '4', '5'], special: ['14'] },
  }, { now: NOW, id: 'q' }).item
  const qxcBody = recordBody(qxc, { multiple: 1, today: '2026-10-18' })
  assert.equal(qxcBody.numbers.play, 'single')
  assert.equal(qxcBody.numbers.positions.length, 7)
  assert.deepEqual(qxcBody.numbers.positions[6], ['14'])

  const kl8 = addToBasket([], {
    lottery_type: 'kl8',
    numbers: { main: Array.from({ length: 20 }, (_, i) => String(i + 1)) },
    source: 'predict',
  }, { now: NOW, id: 'k' }).item
  assert.equal(lineCost('kl8', kl8.numbers, 1), 184756 * 2)
  const kl8Body = recordBody(kl8, { multiple: 1, today: '2026-10-18' })
  assert.equal(kl8Body.numbers.play, 'pick')
  assert.equal(kl8Body.numbers.pick, 10)
  assert.equal(kl8Body.cost, 184756 * 2)
})
