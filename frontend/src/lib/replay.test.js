import assert from 'node:assert/strict'
import test from 'node:test'

import {
  REPLAY_WINDOWS,
  formatPrize,
  formatReturnRate,
  strategyPayload,
  strategyReplayBlocked,
  ticketPayload,
} from './replay.js'

test('window presets stay short', () => {
  assert.deepEqual(REPLAY_WINDOWS.map((item) => item.id), ['30', '100', '300', 'all'])
})

test('return rate and prize mark reference money', () => {
  assert.equal(formatReturnRate(null, false), '—')
  assert.equal(formatReturnRate(undefined, true), '—')
  assert.equal(formatReturnRate(1.25, false), '125.0%')
  assert.equal(formatReturnRate(0, true), '0.0% 参考')
  assert.equal(formatPrize(10, false), '¥ 10')
  assert.equal(formatPrize(5000000, true), '¥ 5000000 参考')
})

test('pulse is not a replay strategy', () => {
  assert.equal(strategyReplayBlocked('pulse'), true)
  assert.equal(strategyReplayBlocked('hot'), false)
  assert.equal(strategyReplayBlocked('random'), false)
})

test('ticket payload keeps a single bet and infers kl8 pick', () => {
  assert.deepEqual(ticketPayload({
    lotteryType: 'ssq',
    numbers: { main: ['01', '02', '03', '04', '05', '06'], special: ['07'] },
    window: '100',
  }), {
    lottery_type: 'ssq',
    bet_numbers: { main: ['01', '02', '03', '04', '05', '06'], special: ['07'] },
    window: '100',
  })
  const kl8 = ticketPayload({
    lotteryType: 'kl8',
    numbers: { main: ['01', '02'] },
    window: 'all',
  })
  assert.equal(kl8.pick, 2)
  assert.equal(kl8.play, 'pick')
  assert.equal(kl8.window, 'all')
})

test('strategy payload omits empty constraints', () => {
  assert.deepEqual(strategyPayload({
    lotteryType: 'dlt',
    strategy: 'cold',
    constraints: {},
    tickets: 2,
    window: '30',
  }), {
    lottery_type: 'dlt',
    strategy: 'cold',
    tickets: 2,
    window: '30',
  })
  const withRules = strategyPayload({
    lotteryType: 'ssq',
    strategy: 'hot',
    constraints: { include_main: ['03'] },
    tickets: 1,
    window: '300',
  })
  assert.deepEqual(withRules.constraints, { include_main: ['03'] })
})
