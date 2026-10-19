import assert from 'node:assert/strict'
import test from 'node:test'

import {
  BASKET_COVERAGE_DISCLAIMER,
  COVERAGE_HOT_RULE,
  basketCoverage,
  coverageTicketIds,
  formatUncoveredText,
  hotTicketIds,
  writeUncoveredKills,
} from './basketCoverage.js'

function item(id, lotteryType, main, special = []) {
  return { id, lottery_type: lotteryType, numbers: { main, special } }
}

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

function cell(report, zone, n) {
  return report[zone].cells.find((row) => row.n === n)
}

test('空篮给出完整号码池，不标过热', () => {
  const report = basketCoverage('ssq', [])
  assert.equal(report.ok, true)
  assert.equal(report.mode, 'set')
  assert.equal(report.ticketCount, 0)
  assert.equal(report.main.poolSize, 33)
  assert.equal(report.main.covered, 0)
  assert.equal(report.main.uncovered.length, 33)
  assert.deepEqual(report.main.uncovered.slice(0, 2), ['01', '02'])
  assert.deepEqual(report.main.hot, [])
  assert.equal(report.main.cells[0].uncovered, true)
  assert.equal(report.main.cells[0].count, 0)
  assert.equal(report.main.cells[0].heat, 0)
  assert.equal(report.main.cells[0].strength, 0)
  assert.equal(report.special.label, '蓝球')
  assert.equal(report.special.poolSize, 16)
  assert.equal(report.summary, '当前彩种还没有注。')
  assert.equal(report.rule, COVERAGE_HOT_RULE)
  assert.match(report.disclaimer, /不构成投注建议/)
  assert.equal(BASKET_COVERAGE_DISCLAIMER, report.disclaimer)

  const dlt = basketCoverage('dlt', null)
  assert.equal(dlt.ticketCount, 0)
  assert.equal(dlt.main.poolSize, 35)
  assert.equal(dlt.special.label, '后区')
  assert.equal(dlt.special.poolSize, 12)
})

test('未知彩种不编号码池', () => {
  const report = basketCoverage('nope', [item('a', 'nope', ['01'])])
  assert.equal(report.ok, false)
  assert.equal(report.main, null)
  assert.equal(report.special, null)
  assert.equal(report.ticketCount, 0)
  assert.equal(report.summary, '未知彩种')
  assert.equal(formatUncoveredText(report), '')
})

test('单注双色球主号去重计数，特别号分开，没有过热', () => {
  const source = [item('a', 'ssq', ['06', '01', '01', '02', '03', '04', '05'], ['07'])]
  const snapshot = JSON.parse(JSON.stringify(source))
  const report = basketCoverage('ssq', source)
  assert.deepEqual(source, snapshot)
  assert.equal(report.ticketCount, 1)
  assert.equal(report.main.covered, 6)
  assert.equal(report.main.maxCount, 1)
  assert.equal(report.main.totalHits, 6)
  assert.ok(Math.abs(report.main.mean - 6 / 33) < 1e-12)
  assert.equal(cell(report, 'main', '01').count, 1)
  assert.equal(cell(report, 'main', '01').hot, false)
  assert.equal(cell(report, 'main', '01').heat, 1)
  assert.equal(cell(report, 'main', '01').strength, 1)
  assert.equal(cell(report, 'main', '01').uncovered, false)
  assert.equal(report.main.uncovered.includes('01'), false)
  assert.equal(report.main.uncovered.includes('07'), true)
  assert.equal(cell(report, 'special', '07').count, 1)
  assert.equal(cell(report, 'special', '07').hot, false)
  assert.deepEqual(report.main.hot, [])
  assert.deepEqual(report.special.hot, [])
  assert.equal(
    report.summary,
    '主号已覆盖 6/33，未覆盖 27 个，没有过热；蓝球已覆盖 1/16，未覆盖 15 个，没有过热',
  )
})

test('多注重叠时重复号过热，只出现一次的不过热，别的彩种不算', () => {
  const report = basketCoverage('ssq', [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['07']),
    item('b', 'ssq', ['01', '02', '08', '09', '10', '11'], ['08']),
    item('c', 'dlt', ['01', '02', '03', '04', '05'], ['01', '02']),
    null,
  ])
  assert.equal(report.ticketCount, 2)
  assert.equal(cell(report, 'main', '01').count, 2)
  assert.equal(cell(report, 'main', '01').hot, true)
  assert.equal(cell(report, 'main', '01').strength, 1)
  assert.equal(cell(report, 'main', '01').heat, 5)
  assert.equal(cell(report, 'main', '03').count, 1)
  assert.equal(cell(report, 'main', '03').hot, false)
  assert.equal(cell(report, 'main', '03').strength, 0.5)
  assert.equal(cell(report, 'main', '03').heat, 3)
  assert.equal(cell(report, 'main', '33').count, 0)
  assert.equal(cell(report, 'main', '33').uncovered, true)
  assert.deepEqual(report.main.hot, ['01', '02'])
  assert.equal(cell(report, 'special', '07').count, 1)
  assert.equal(cell(report, 'special', '08').count, 1)
  assert.deepEqual(report.special.hot, [])
  assert.match(report.summary, /过热 01、02/)
})

test('大乐透后区单独计数，同号两注算过热且不进前区', () => {
  const report = basketCoverage('dlt', [
    item('a', 'dlt', ['01', '02', '03', '04', '05'], ['01', '01', '02']),
    item('b', 'dlt', ['06', '07', '08', '09', '10'], ['01', '03']),
  ])
  assert.equal(cell(report, 'main', '01').count, 1)
  assert.equal(cell(report, 'special', '01').count, 2)
  assert.equal(cell(report, 'special', '01').hot, true)
  assert.equal(cell(report, 'special', '02').count, 1)
  assert.equal(cell(report, 'special', '02').hot, false)
  assert.deepEqual(report.main.hot, [])
  assert.deepEqual(report.special.hot, ['01'])
})

test('七乐彩和快乐八没有特别号区，快乐八按集合去重', () => {
  const qlc = basketCoverage('qlc', [
    item('a', 'qlc', ['01', '02', '03', '04', '05', '06', '07'], ['08']),
  ])
  assert.equal(qlc.special, null)
  assert.equal(qlc.main.poolSize, 30)
  assert.equal(cell(qlc, 'main', '08').count, 0)
  assert.match(qlc.summary, /^主号已覆盖 7\/30/)
  assert.doesNotMatch(qlc.summary, /特别/)

  const kl8 = basketCoverage('kl8', [item('a', 'kl8', ['1', '01', '80', '02'])])
  assert.equal(kl8.special, null)
  assert.equal(kl8.main.poolSize, 80)
  assert.equal(kl8.main.covered, 3)
  assert.equal(cell(kl8, 'main', '01').count, 1)
  assert.equal(cell(kl8, 'main', '02').count, 1)
  assert.equal(cell(kl8, 'main', '80').count, 1)
})

test('福彩3D按位保留重复，各位落入 0–9', () => {
  const report = basketCoverage('fc3d', [
    item('a', 'fc3d', ['1', '1', '1']),
    item('b', 'fc3d', ['1', '2', '9']),
  ])
  assert.equal(report.mode, 'digit')
  assert.equal(report.main.poolSize, 10)
  assert.equal(report.special, null)
  assert.equal(cell(report, 'main', '1').count, 4)
  assert.equal(cell(report, 'main', '2').count, 1)
  assert.equal(cell(report, 'main', '9').count, 1)
  assert.equal(cell(report, 'main', '0').count, 0)
  assert.equal(cell(report, 'main', '1').hot, true)
  assert.equal(cell(report, 'main', '2').hot, false)
  assert.equal(cell(report, 'main', '1').heat, 5)
  assert.equal(cell(report, 'main', '2').strength, 0.25)
  assert.equal(cell(report, 'main', '2').heat, 2)
  assert.deepEqual(report.main.hot, ['1'])
  assert.deepEqual(report.main.uncovered, ['0', '3', '4', '5', '6', '7', '8'])
})

test('排列五次数拉平且不少于 2 时，没有号高于平均，不算过热', () => {
  const report = basketCoverage('pl5', [
    item('a', 'pl5', ['0', '1', '2', '3', '4']),
    item('b', 'pl5', ['5', '6', '7', '8', '9']),
    item('c', 'pl5', ['0', '1', '2', '3', '4']),
    item('d', 'pl5', ['5', '6', '7', '8', '9']),
  ])
  assert.equal(report.main.poolSize, 10)
  assert.equal(report.main.maxCount, 2)
  assert.equal(report.main.covered, 10)
  assert.equal(report.main.totalHits, 20)
  assert.equal(report.main.mean, 2)
  assert.equal(report.main.hot.length, 0)
  assert.equal(report.main.cells.every((row) => row.count === 2 && row.heat === 5 && row.hot === false), true)
  assert.match(report.summary, /没有过热/)
})

test('七星彩特别号不并进主号，主号重复按位累计', () => {
  const report = basketCoverage('qxc', [
    item('a', 'qxc', ['7', '7', '7', '7', '7', '7'], ['7']),
    item('b', 'qxc', ['7', '1', '2', '3', '4', '5'], ['14']),
  ])
  assert.equal(cell(report, 'main', '7').count, 7)
  assert.equal(cell(report, 'main', '7').hot, true)
  assert.equal(report.special.poolSize, 15)
  assert.equal(report.special.label, '特别号')
  assert.equal(cell(report, 'special', '7').count, 1)
  assert.equal(cell(report, 'special', '14').count, 1)
  assert.equal(cell(report, 'special', '7').hot, false)
  assert.equal(report.main.cells.length, 10)
})

test('越界号码跳过，过热名单过长时摘要只点前 8 个', () => {
  const report = basketCoverage('pl3', [
    item('a', 'pl3', ['1', 'x', '99']),
    item('b', 'ssq', ['01', '02', '03', '04', '05', '06'], ['01']),
  ])
  assert.equal(report.ticketCount, 1)
  assert.equal(cell(report, 'main', '1').count, 1)
  assert.equal(report.main.covered, 1)

  const crowded = basketCoverage('ssq', [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['01']),
    item('b', 'ssq', ['04', '05', '06', '07', '08', '09'], ['01']),
    item('c', 'ssq', ['01', '02', '03', '07', '08', '09'], ['02']),
  ])
  assert.equal(crowded.main.hot.length, 9)
  assert.match(crowded.summary, /过热 01、02、03、04、05、06、07、08 等 9 个/)
})

test('复制未覆盖带上分区，空篮和铺满分开', () => {
  assert.equal(formatUncoveredText(basketCoverage('ssq', [])), '')
  const text = formatUncoveredText(basketCoverage('ssq', [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['01']),
  ]))
  assert.match(text, /^双色球未覆盖/)
  assert.match(text, /主号 07 08/)
  assert.match(text, /蓝球 02 03/)
  assert.match(text, /不构成投注建议/)
  assert.doesNotMatch(text, /主号 01/)
  assert.doesNotMatch(text, /蓝球 01/)

  const full = formatUncoveredText(basketCoverage('fc3d', [
    item('a', 'fc3d', ['0', '1', '2']),
    item('b', 'fc3d', ['3', '4', '5']),
    item('c', 'fc3d', ['6', '7', '8']),
    item('d', 'fc3d', ['9', '0', '1']),
  ]))
  assert.match(full, /福彩3D未覆盖/)
  assert.match(full, /主号已铺满/)
})

test('点选号码找出含该号的注，数字彩重复只记一注', () => {
  const items = [
    item('a', 'fc3d', ['1', '1', '2']),
    item('b', 'fc3d', ['3', '4', '5']),
    item('c', 'ssq', ['01', '02', '03', '04', '05', '06'], ['01']),
  ]
  assert.deepEqual(coverageTicketIds('fc3d', items, 'main', '1'), ['a'])
  assert.deepEqual(coverageTicketIds('fc3d', items, 'main', 1), ['a'])
  assert.deepEqual(coverageTicketIds('fc3d', items, 'main', '9'), [])
  assert.deepEqual(coverageTicketIds('fc3d', items, 'special', '1'), [])
  assert.deepEqual(coverageTicketIds('ssq', items, 'special', '1'), ['c'])
  assert.deepEqual(coverageTicketIds('ssq', items, 'main', '01'), ['c'])
  assert.deepEqual(coverageTicketIds('ssq', items, 'main', '07'), [])
  assert.deepEqual(coverageTicketIds('nope', items, 'main', '1'), [])
})

test('过热注是含过热号的注', () => {
  const items = [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['07']),
    item('b', 'ssq', ['01', '07', '08', '09', '10', '11'], ['08']),
    item('c', 'ssq', ['12', '13', '14', '15', '16', '17'], ['09']),
  ]
  const report = basketCoverage('ssq', items)
  assert.deepEqual(report.main.hot, ['01'])
  assert.deepEqual(hotTicketIds('ssq', items, report), ['a', 'b'])
  assert.deepEqual(hotTicketIds('ssq', items, basketCoverage('ssq', [])), [])
})

test('未覆盖写入杀号：合并已有杀号，跳过胆码，保留其他条件', () => {
  const report = basketCoverage('ssq', [
    item('a', 'ssq', ['01', '02', '03', '04', '05', '06'], ['01']),
  ])
  const storage = memoryStorage({
    'yysg.predict.constraints.ssq': JSON.stringify({
      include_main: ['07'],
      exclude_main: ['08'],
      include_special: ['02'],
      exclude_special: [],
      sum_min: 80,
      odd_min: 2,
    }),
    'yysg.predict.constraints.dlt': JSON.stringify({ exclude_main: ['01'] }),
  })
  const result = writeUncoveredKills(storage, 'ssq', report)
  assert.equal(result.ok, true)
  assert.equal(result.status, 'written')
  assert.equal(result.addedMain.length, 25)
  assert.equal(result.addedMain[0], '09')
  assert.equal(result.addedMain.at(-1), '33')
  assert.deepEqual(result.skippedMain, ['07'])
  assert.equal(result.addedSpecial.length, 14)
  assert.equal(result.addedSpecial[0], '03')
  assert.deepEqual(result.skippedSpecial, ['02'])
  assert.equal(result.message, '已把未覆盖写入杀号：主号 25 个，蓝球 14 个。胆码未改')
  const stored = JSON.parse(storage.getItem('yysg.predict.constraints.ssq'))
  assert.equal(stored.sum_min, 80)
  assert.equal(stored.odd_min, 2)
  assert.deepEqual(stored.include_main, ['07'])
  assert.deepEqual(stored.include_special, ['02'])
  assert.equal(stored.exclude_main.includes('08'), true)
  assert.equal(stored.exclude_main.includes('09'), true)
  assert.equal(stored.exclude_main.includes('33'), true)
  assert.equal(stored.exclude_main.includes('01'), false)
  assert.equal(stored.exclude_main.includes('07'), false)
  assert.equal(stored.exclude_special.includes('02'), false)
  assert.equal(stored.exclude_special.includes('03'), true)
  assert.deepEqual(JSON.parse(storage.getItem('yysg.predict.constraints.dlt')).exclude_main, ['01'])
})

test('空篮、铺满、已写入和胆码挡下时，杀号按说的做', () => {
  const emptyStorage = memoryStorage()
  const empty = writeUncoveredKills(emptyStorage, 'ssq', basketCoverage('ssq', []))
  assert.equal(empty.ok, false)
  assert.equal(empty.status, 'empty')
  assert.equal(empty.message, '当前彩种还没有注')
  assert.equal(emptyStorage.getItem('yysg.predict.constraints.ssq'), null)

  const fullKey = 'yysg.predict.constraints.fc3d'
  const fullStorage = memoryStorage({ [fullKey]: '{"sum_min":9}' })
  const full = writeUncoveredKills(fullStorage, 'fc3d', basketCoverage('fc3d', [
    item('a', 'fc3d', ['0', '1', '2']),
    item('b', 'fc3d', ['3', '4', '5']),
    item('c', 'fc3d', ['6', '7', '8']),
    item('d', 'fc3d', ['9', '9', '9']),
  ]))
  assert.equal(full.status, 'full')
  assert.equal(full.message, '号码池已经铺满，没有可写入的杀号')
  assert.equal(fullStorage.getItem(fullKey), '{"sum_min":9}')

  const sameStorage = memoryStorage({
    'yysg.predict.constraints.pl3': JSON.stringify({
      exclude_main: ['3', '4', '5', '6', '7', '8', '9'],
    }),
  })
  const same = writeUncoveredKills(sameStorage, 'pl3', basketCoverage('pl3', [
    item('a', 'pl3', ['0', '1', '2']),
  ]))
  assert.equal(same.status, 'unchanged')
  assert.deepEqual(same.addedMain, [])
  assert.equal(same.message, '这些未覆盖号已经在杀号里')

  const danStorage = memoryStorage({
    'yysg.predict.constraints.pl3': JSON.stringify({ include_main: ['3', '4', '5', '6', '7', '8', '9'] }),
  })
  const blocked = writeUncoveredKills(danStorage, 'pl3', basketCoverage('pl3', [
    item('a', 'pl3', ['0', '1', '2']),
  ]))
  assert.equal(blocked.status, 'skipped')
  assert.equal(blocked.message, '未覆盖的号都是胆码，没有改杀号')
  const storedDan = JSON.parse(danStorage.getItem('yysg.predict.constraints.pl3'))
  assert.equal(storedDan.exclude_main, undefined)
  assert.deepEqual(storedDan.include_main, ['3', '4', '5', '6', '7', '8', '9'])

  const broken = memoryStorage({ 'yysg.predict.constraints.pl3': '{oops' })
  const repaired = writeUncoveredKills(broken, 'pl3', basketCoverage('pl3', [
    item('a', 'pl3', ['0', '1', '2']),
  ]))
  assert.equal(repaired.ok, true)
  const stored = JSON.parse(broken.getItem('yysg.predict.constraints.pl3'))
  assert.deepEqual(stored.exclude_main, ['3', '4', '5', '6', '7', '8', '9'])
  assert.equal(stored.sum_min, '')

  const unknown = writeUncoveredKills(memoryStorage(), 'nope', basketCoverage('nope', []))
  assert.equal(unknown.ok, false)
  assert.equal(unknown.status, 'invalid')
})

test('数字彩只把未覆盖主号写入杀号，不动特别号条件', () => {
  const report = basketCoverage('fc3d', [item('a', 'fc3d', ['1', '1', '1'])])
  const storage = memoryStorage({
    'yysg.predict.constraints.fc3d': JSON.stringify({
      exclude_special: ['1'],
      sum_max: 20,
    }),
  })
  const result = writeUncoveredKills(storage, 'fc3d', report)
  assert.deepEqual(result.addedMain, ['0', '2', '3', '4', '5', '6', '7', '8', '9'])
  assert.deepEqual(result.addedSpecial, [])
  assert.equal(result.message, '已把未覆盖写入杀号：主号 9 个')
  const stored = JSON.parse(storage.getItem('yysg.predict.constraints.fc3d'))
  assert.deepEqual(stored.exclude_special, ['1'])
  assert.equal(stored.sum_max, 20)
  assert.equal(stored.exclude_main.includes('1'), false)
})
