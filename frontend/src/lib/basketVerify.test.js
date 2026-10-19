import assert from 'node:assert/strict'
import test from 'node:test'

import { addToBasket } from './basket.js'
import {
  betHitView,
  formatMoney,
  formatSignedMoney,
  isIllustrativeWin,
  netClass,
  ticketsFromBasket,
  verifyStatusText,
} from './basketVerify.js'

test('basket tickets follow the same play shape as a purchase record', () => {
  let items = []
  items = addToBasket(items, {
    lottery_type: 'ssq',
    numbers: { main: ['6', '1', '3', '2', '5', '4'], special: ['9'] },
    source: 'manual',
  }, { id: 's1' }).items
  items = addToBasket(items, {
    lottery_type: 'kl8',
    numbers: { main: Array.from({ length: 12 }, (_, index) => String(index + 1)) },
  }, { id: 'k1' }).items
  items = addToBasket(items, {
    lottery_type: 'fc3d',
    numbers: { main: ['1', '2', '3'], special: [] },
  }, { id: 'd1' }).items

  const tickets = ticketsFromBasket(items, 3)
  assert.equal(tickets.length, 3)
  assert.equal(tickets[0].id, 's1')
  assert.equal(tickets[0].play, 'single')
  assert.deepEqual(tickets[0].numbers.main, ['01', '02', '03', '04', '05', '06'])
  assert.deepEqual(tickets[0].numbers.special, ['09'])
  assert.equal(tickets[0].numbers.multiple, 3)
  assert.equal(tickets[1].play, 'pick')
  assert.equal(tickets[1].pick, 10)
  assert.equal(tickets[1].numbers.pick, 10)
  assert.equal(tickets[1].numbers.main.length, 12)
  assert.equal(tickets[2].play, 'direct')
  assert.deepEqual(tickets[2].numbers.positions, [['1'], ['2'], ['3']])
  assert.equal(tickets[2].numbers.multiple, 3)
})

test('hit marks light matching balls and leave misses dark', () => {
  const ssq = betHitView(
    'ssq',
    { main: ['01', '02', '03', '04', '05', '06'], special: ['16'] },
    { main: ['01', '02', '03', '11', '12', '13'], special: ['16'] },
  )
  assert.deepEqual(ssq.marks.main, [true, true, true, false, false, false])
  assert.deepEqual(ssq.marks.special, [true])
  assert.equal(ssq.count, 4)

  const miss = betHitView(
    'ssq',
    { main: ['21', '22', '23', '24', '25', '26'], special: ['01'] },
    { main: ['01', '02', '03', '04', '05', '06'], special: ['16'] },
  )
  assert.equal(miss.count, 0)
  assert.ok(miss.marks.main.every((flag) => flag === false))
  assert.deepEqual(miss.marks.special, [false])
})

test('digit and qlc hits stay positional or include the special ball', () => {
  const digit = betHitView(
    'fc3d',
    { positions: [['1', '2'], ['2'], ['9']] },
    { main: ['1', '2', '3'] },
  )
  assert.deepEqual(digit.marks.positions, [[true, false], [true], [false]])
  assert.equal(digit.count, 2)
  assert.deepEqual(digit.numbers.positions, [['1', '2'], ['2'], ['9']])

  const qlc = betHitView(
    'qlc',
    { main: ['01', '02', '03', '04', '05', '06', '30'] },
    { main: ['01', '02', '03', '04', '05', '06', '07'], special: ['30'] },
  )
  assert.deepEqual(qlc.marks.main, [true, true, true, true, true, true, true])
  assert.equal(qlc.count, 7)
})

test('money, win flag, and net tone stay display-only', () => {
  assert.equal(formatMoney(5), '¥ 5')
  assert.equal(formatMoney(4.6), '¥ 4.60')
  assert.equal(formatMoney(null), '—')
  assert.equal(formatSignedMoney(12), '+¥ 12')
  assert.equal(formatSignedMoney(-4), '-¥ 4')
  assert.equal(formatSignedMoney(0), '¥ 0')
  assert.equal(verifyStatusText({ status: 'ok', level: '六等奖', amount: 5 }), '六等奖')
  assert.equal(verifyStatusText({ status: 'ok', level: '未中奖', amount: 0 }), '未中奖')
  assert.equal(verifyStatusText({ status: 'no_draw', amount: 0 }), '无开奖')
  assert.equal(verifyStatusText({ status: 'error', message: '开奖号码不完整' }), '开奖号码不完整')
  assert.equal(isIllustrativeWin({ status: 'ok', amount: 5 }), true)
  assert.equal(isIllustrativeWin({ status: 'ok', amount: 0 }), false)
  assert.equal(isIllustrativeWin({ status: 'no_draw', amount: 5 }), false)
  assert.equal(isIllustrativeWin({ status: 'error', amount: 5 }), false)
  assert.equal(netClass(12), 'ok')
  assert.equal(netClass(-4), 'down')
  assert.equal(netClass(0), '')
})
