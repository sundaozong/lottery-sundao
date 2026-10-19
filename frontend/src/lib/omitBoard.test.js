import assert from 'node:assert/strict'
import test from 'node:test'

import { addToBasket } from './basket.js'
import {
  blankPredictConstraints,
  coldTicket,
  constraintStorageKey,
  emptyMarks,
  hasConstraintMarks,
  heatTone,
  markOf,
  mergePredictConstraints,
  omitSummary,
  toggleMark,
  writePredictConstraints,
} from './omitBoard.js'

test('刚开出是热，高比值或偏冷是冷，比值到 1 是凉', () => {
  assert.equal(heatTone({ current: 0, count: 3, ratio: 0, cold: false }), 'hot')
  assert.equal(heatTone({ current: 12, count: 2, ratio: 2, cold: true }), 'cold')
  assert.equal(heatTone({ current: 6, count: 0, ratio: 1, cold: true }), 'cold')
  assert.equal(heatTone({ current: 4, count: 2, ratio: 1, cold: false }), 'cool')
  assert.equal(heatTone({ current: 1, count: 4, ratio: 0.4, cold: false }), 'warm')
})

test('选胆和选杀互斥，胆码满了不再加', () => {
  let marks = emptyMarks()
  let step = toggleMark('ssq', marks, 'main', '3', 'dan')
  assert.equal(step.status, 'added')
  assert.deepEqual(step.marks.danMain, ['03'])
  step = toggleMark('ssq', step.marks, 'main', '03', 'kill')
  assert.deepEqual(step.marks.danMain, [])
  assert.deepEqual(step.marks.killMain, ['03'])
  step = toggleMark('ssq', step.marks, 'main', '03', 'dan')
  assert.deepEqual(step.marks.danMain, ['03'])
  assert.deepEqual(step.marks.killMain, [])

  marks = emptyMarks()
  for (const n of ['01', '02', '03', '04', '05', '06']) {
    marks = toggleMark('ssq', marks, 'main', n, 'dan').marks
  }
  const full = toggleMark('ssq', marks, 'main', '07', 'dan')
  assert.equal(full.status, 'full')
  assert.deepEqual(full.marks.danMain, ['01', '02', '03', '04', '05', '06'])

  const blue = toggleMark('ssq', full.marks, 'special', '9', 'dan')
  assert.deepEqual(blue.marks.danSpecial, ['09'])
  const second = toggleMark('ssq', blue.marks, 'special', '10', 'dan')
  assert.equal(second.status, 'full')
  assert.equal(markOf(blue.marks, 'special', '09'), 'dan')
  assert.equal(markOf(blue.marks, 'main', '01'), 'dan')
})

test('点选组注沿用走势规则，再点一次取消', () => {
  let marks = emptyMarks()
  let step = toggleMark('fc3d', marks, 'main', '1', 'pick')
  step = toggleMark('fc3d', step.marks, 'main', '1', 'pick')
  step = toggleMark('fc3d', step.marks, 'main', '2', 'pick')
  assert.deepEqual(step.marks.pick.main, ['1', '1', '2'])
  assert.equal(markOf(step.marks, 'main', '1'), 'pick')
  step = toggleMark('fc3d', step.marks, 'main', '1', 'pick')
  assert.deepEqual(step.marks.pick.main, ['1', '2'])
})

test('写入机选条件只替换胆杀，保留奇偶与和值', () => {
  const existing = blankPredictConstraints()
  existing.include_main = ['05']
  existing.odd_min = 2
  existing.sum_min = 80
  const marks = {
    ...emptyMarks(),
    danMain: ['01', '03'],
    killMain: ['01', '02'],
    danSpecial: ['08'],
    killSpecial: ['01'],
  }
  const next = mergePredictConstraints(existing, marks, 'ssq')
  assert.deepEqual(next.include_main, ['01', '03'])
  assert.deepEqual(next.exclude_main, ['02'])
  assert.deepEqual(next.include_special, ['08'])
  assert.deepEqual(next.exclude_special, ['01'])
  assert.equal(next.odd_min, 2)
  assert.equal(next.sum_min, 80)
  assert.equal(hasConstraintMarks(marks), true)
  assert.equal(hasConstraintMarks(emptyMarks()), false)

  const digit = mergePredictConstraints(existing, marks, 'fc3d')
  assert.deepEqual(digit.include_special, [])
  assert.deepEqual(digit.exclude_special, [])

  const storage = new Map()
  const stored = writePredictConstraints({
    setItem(key, value) { storage.set(key, value) },
  }, 'ssq', marks)
  assert.equal(constraintStorageKey('ssq'), 'yysg.predict.constraints.ssq')
  assert.deepEqual(JSON.parse(storage.get('yysg.predict.constraints.ssq')).include_main, ['01', '03'])
  assert.deepEqual(stored.exclude_main, ['02'])
})

test('冷号按比值从高到低组一注，不够就说明', () => {
  const ssq = coldTicket('ssq', {
    main: [
      { n: '03', ratio: 4, current: 12, cold: true },
      { n: '01', ratio: 3, current: 9, cold: true },
      { n: '11', ratio: 2.5, current: 8, cold: true },
      { n: '02', ratio: 2, current: 7, cold: true },
      { n: '08', ratio: 1.8, current: 6, cold: true },
      { n: '16', ratio: 1.6, current: 5, cold: true },
      { n: '05', ratio: 4.2, current: 1, cold: false },
    ],
    special: [
      { n: '09', ratio: 2, current: 6, cold: true },
      { n: '01', ratio: 3, current: 1, cold: false },
    ],
  })
  assert.equal(ssq.ok, true)
  assert.deepEqual(ssq.numbers.main, ['01', '02', '03', '08', '11', '16'])
  assert.deepEqual(ssq.numbers.special, ['09'])
  const basket = addToBasket([], { lottery_type: 'ssq', numbers: ssq.numbers, source: 'omit', note: '遗漏偏冷' })
  assert.equal(basket.status, 'added')

  const short = coldTicket('ssq', {
    main: [{ n: '01', ratio: 2, current: 4, cold: true }],
    special: [{ n: '02', ratio: 2, current: 4, cold: true }],
  })
  assert.equal(short.ok, false)
  assert.match(short.message, /偏冷/)

  const digit = coldTicket('fc3d', {
    main: [
      { n: '1', ratio: 1.2, current: 4, cold: true },
      { n: '7', ratio: 3, current: 9, cold: true },
      { n: '0', ratio: 2, current: 8, cold: true },
    ],
    special: [],
  })
  assert.deepEqual(digit.numbers.main, ['7', '0', '1'])

  const kl8main = Array.from({ length: 12 }, (_, i) => ({
    n: String(i + 1).padStart(2, '0'),
    ratio: 12 - i,
    current: 12 - i,
    cold: true,
  }))
  const kl8 = coldTicket('kl8', { main: kl8main, special: [] })
  assert.equal(kl8.ok, true)
  assert.equal(kl8.numbers.main.length, 10)
  assert.deepEqual(kl8.numbers.main, ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10'])
})

test('遗漏摘要是可粘贴的纯文本', () => {
  const text = omitSummary({
    sample_size: 80,
    main: [{ n: '03', current: 12, avg: 4, ratio: 3, cold: true }],
    special: [{ n: '09', current: 8, avg: 3, ratio: 2.5, cold: true }],
  }, '双色球')
  assert.match(text, /双色球/)
  assert.match(text, /80/)
  assert.match(text, /03/)
  assert.match(text, /当前12/)
  assert.match(text, /09/)
  assert.match(text, /仅供娱乐/)
  assert.match(text, /不构成投注建议/)
  assert.equal(text.includes('<'), false)
})
