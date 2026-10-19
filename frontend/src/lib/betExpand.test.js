import assert from 'node:assert/strict'
import test from 'node:test'

import { addManyToBasket, sourceLabel } from './basket.js'
import { basketDrafts, parseBalls, ticketKey } from './betExpand.js'

test('粘贴号码会补零、去重，并丢掉越界', () => {
  const zone = { lo: 1, hi: 33, width: 2 }
  const parsed = parseBalls('3,03 34 ab 7', zone)
  assert.deepEqual(parsed.balls, ['03', '07'])
  assert.deepEqual(parsed.invalid, ['34', 'ab'])
})

test('超过上限时保留最小的号码', () => {
  const cut = parseBalls('9 1 3', { lo: 0, hi: 9, width: 1 }, 2)
  assert.deepEqual(cut.balls, ['1', '3'])
  assert.deepEqual(cut.invalid, [])
})

test('展开的单注放进选号篮，相同号码不再重复放入', () => {
  const ticket = { main: ['01', '02', '03', '04', '05', '06'], special: ['07'] }
  const drafts = basketDrafts('ssq', [ticket, ticket])
  assert.equal(ticketKey(ticket), '01,02,03,04,05,06|07')
  const once = addManyToBasket([], [drafts[0]])
  assert.equal(once.added, 1)
  assert.equal(sourceLabel(once.items[0]), '复式胆拖')
  const twice = addManyToBasket(once.items, drafts)
  assert.equal(twice.added, 0)
  assert.equal(twice.duplicates, 2)
  assert.equal(twice.items.length, 1)
})
