import assert from 'node:assert/strict'
import test from 'node:test'

import { constraintStorageKey } from './omitBoard.js'
import {
  PRESET_STORAGE_KEY,
  applyPreset,
  builtinPresets,
  deletePreset,
  exportPresetText,
  importPresetText,
  listPresets,
  renamePreset,
  savePreset,
} from './constraintPresets.js'

const NOW = '2026-10-19T01:00:00.000Z'
const LATER = '2026-10-19T02:00:00.000Z'

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

function panelKeys(constraints) {
  return [
    'include_main',
    'exclude_main',
    'include_special',
    'exclude_special',
    'odd_min',
    'odd_max',
    'sum_min',
    'sum_max',
    'span_min',
    'span_max',
    'max_consecutive',
    'big_min',
    'big_max',
    'zone1',
    'zone2',
    'zone3',
  ].every((key) => Object.prototype.hasOwnProperty.call(constraints, key))
}

test('双色球和大乐透内置均衡方案含奇偶、中和值与连号上限，且不能删除', () => {
  const ssq = builtinPresets('ssq')
  const balance = ssq.find((item) => item.name === '均衡')
  const shortRun = ssq.find((item) => item.name === '少连号')
  assert.ok(balance)
  assert.ok(shortRun)
  assert.equal(balance.builtin, true)
  assert.equal(balance.lottery_type, 'ssq')
  assert.equal(balance.strategy, '')
  assert.equal(panelKeys(balance.constraints), true)
  assert.equal(balance.constraints.odd_min, 3)
  assert.equal(balance.constraints.odd_max, 3)
  assert.equal(balance.constraints.sum_min, 80)
  assert.equal(balance.constraints.sum_max, 130)
  assert.equal(balance.constraints.max_consecutive, 2)
  assert.deepEqual(balance.constraints.include_main, [])

  const dlt = builtinPresets('dlt').find((item) => item.name === '均衡')
  assert.equal(dlt.constraints.odd_min, 2)
  assert.equal(dlt.constraints.odd_max, 3)
  assert.equal(dlt.constraints.sum_min, 60)
  assert.equal(dlt.constraints.sum_max, 120)
  assert.equal(dlt.constraints.max_consecutive, 2)

  const blocked = deletePreset(memoryStorage(), 'ssq', balance.id)
  assert.equal(blocked.ok, false)
  assert.equal(blocked.status, 'builtin')
  assert.match(blocked.message, /不能删除/)
})

test('数字彩内置方案是和值中段与奇偶均衡，不含连号', () => {
  const presets = builtinPresets('fc3d')
  const mid = presets.find((item) => item.name === '中段均衡')
  const odd = presets.find((item) => item.name === '奇偶均衡')
  assert.ok(mid)
  assert.ok(odd)
  assert.equal(mid.lottery_type, 'fc3d')
  assert.equal(mid.constraints.sum_min, 9)
  assert.equal(mid.constraints.sum_max, 18)
  assert.equal(mid.constraints.odd_min, 1)
  assert.equal(mid.constraints.odd_max, 2)
  assert.equal(mid.constraints.max_consecutive, '')
  assert.equal(odd.constraints.odd_min, 1)
  assert.equal(odd.constraints.odd_max, 2)
  assert.equal(odd.constraints.sum_min, '')
  assert.equal(builtinPresets('pl5').find((item) => item.name === '中段均衡').constraints.max_consecutive, '')
})

test('保存、覆盖、改名、删除我的方案，同名冲突会提示', () => {
  const storage = memoryStorage()
  const saved = savePreset(storage, {
    lotteryType: 'ssq',
    name: '周末',
    strategy: 'hot',
    constraints: { odd_min: 2, odd_max: 4, include_main: ['03'] },
  }, { now: () => NOW })
  assert.equal(saved.ok, true)
  assert.equal(saved.preset.builtin, false)
  assert.equal(saved.preset.strategy, 'hot')
  assert.equal(saved.preset.updated_at, NOW)
  assert.equal(saved.preset.constraints.odd_min, 2)
  assert.deepEqual(saved.preset.constraints.include_main, ['03'])

  const conflict = savePreset(storage, {
    lotteryType: 'ssq',
    name: '周末',
    constraints: { odd_min: 1 },
  }, { now: () => LATER })
  assert.equal(conflict.ok, false)
  assert.equal(conflict.status, 'conflict')
  assert.match(conflict.message, /覆盖/)
  assert.match(conflict.message, /改名/)

  const overwritten = savePreset(storage, {
    lotteryType: 'ssq',
    name: '周末',
    strategy: 'cold',
    constraints: { odd_min: 1, odd_max: 2 },
  }, { overwrite: true, now: () => LATER })
  assert.equal(overwritten.ok, true)
  assert.equal(overwritten.preset.id, saved.preset.id)
  assert.equal(overwritten.preset.constraints.odd_min, 1)
  assert.equal(overwritten.preset.constraints.odd_max, 2)
  assert.equal(overwritten.preset.strategy, 'cold')
  assert.equal(overwritten.preset.updated_at, LATER)
  assert.equal(listPresets(storage, 'ssq').filter((item) => !item.builtin).length, 1)

  const renamed = renamePreset(storage, 'ssq', saved.preset.id, '工作日', { now: () => '2026-10-19T03:00:00.000Z' })
  assert.equal(renamed.ok, true)
  assert.equal(renamed.preset.name, '工作日')

  const removed = deletePreset(storage, 'ssq', saved.preset.id)
  assert.equal(removed.ok, true)
  assert.equal(listPresets(storage, 'ssq').some((item) => !item.builtin), false)
})

test('内置方案名不能覆盖，另存新名字可以', () => {
  const storage = memoryStorage()
  const blocked = savePreset(storage, {
    lotteryType: 'ssq',
    name: '均衡',
    constraints: builtinPresets('ssq')[0].constraints,
  }, { overwrite: true })
  assert.equal(blocked.ok, false)
  assert.equal(blocked.status, 'builtin')
  assert.match(blocked.message, /另存|改名/)

  const copy = savePreset(storage, {
    lotteryType: 'ssq',
    name: '我的均衡',
    strategy: 'hybrid',
    constraints: builtinPresets('ssq').find((item) => item.name === '均衡').constraints,
  })
  assert.equal(copy.ok, true)
  assert.equal(copy.preset.builtin, false)
  assert.equal(copy.preset.constraints.max_consecutive, 2)
  assert.equal(renamePreset(storage, 'ssq', copy.preset.id, '少连号').status, 'builtin')
})

test('方案按彩种隔离，别的彩种可以用同名', () => {
  const storage = memoryStorage()
  assert.equal(savePreset(storage, {
    lotteryType: 'ssq',
    name: '周末',
    constraints: { sum_min: 80 },
  }).ok, true)
  assert.equal(savePreset(storage, {
    lotteryType: 'dlt',
    name: '周末',
    constraints: { sum_min: 70 },
  }).ok, true)

  const dlt = listPresets(storage, 'dlt')
  assert.equal(dlt.every((item) => item.lottery_type === 'dlt'), true)
  const mine = dlt.find((item) => item.name === '周末')
  assert.equal(mine.builtin, false)
  assert.equal(mine.constraints.sum_min, 70)
  assert.equal(listPresets(storage, 'ssq').find((item) => item.name === '周末').constraints.sum_min, 80)
})

test('脉动不能存成方案策略', () => {
  const storage = memoryStorage()
  const saved = savePreset(storage, {
    lotteryType: 'ssq',
    name: '脉动套用',
    strategy: 'pulse',
    constraints: { odd_min: 3 },
  })
  assert.equal(saved.ok, false)
  assert.equal(saved.status, 'strategy')
  assert.match(saved.message, /热号|冷号|混合|随机/)
  assert.equal(storage.getItem(PRESET_STORAGE_KEY), null)
})

test('套用后面板字段与草稿一致，并接受预测接口的条件字段', () => {
  const storage = memoryStorage()
  const text = JSON.stringify({
    name: '导入均衡',
    lottery_type: 'ssq',
    strategy: 'hybrid',
    constraints: {
      include_main: ['01', '07'],
      odd_count: 3,
      sum_min: 90,
      sum_max: 120,
      zone_counts: [2, 2, 2],
      max_consecutive: 2,
      big_count: 3,
    },
  })
  const imported = importPresetText(storage, 'ssq', text, { now: () => NOW })
  assert.equal(imported.ok, true)
  const applied = applyPreset(storage, imported.preset)
  assert.equal(applied.ok, true)
  assert.equal(applied.strategy, 'hybrid')
  assert.deepEqual(applied.constraints.include_main, ['01', '07'])
  assert.equal(applied.constraints.odd_min, 3)
  assert.equal(applied.constraints.odd_max, 3)
  assert.equal(applied.constraints.sum_min, 90)
  assert.equal(applied.constraints.sum_max, 120)
  assert.equal(applied.constraints.zone1, 2)
  assert.equal(applied.constraints.zone2, 2)
  assert.equal(applied.constraints.zone3, 2)
  assert.equal(applied.constraints.max_consecutive, 2)
  assert.equal(applied.constraints.big_min, 3)
  assert.equal(applied.constraints.big_max, 3)
  assert.deepEqual(applied.constraints, imported.preset.constraints)
  const draft = JSON.parse(storage.getItem(constraintStorageKey('ssq')))
  assert.deepEqual(draft, applied.constraints)
  assert.equal(storage.getItem(constraintStorageKey('dlt')), null)
})

test('导入非法 JSON、缺字段、跨彩种和脉动策略时给出中文提示', () => {
  const storage = memoryStorage()
  const badJson = importPresetText(storage, 'ssq', '{oops')
  assert.equal(badJson.ok, false)
  assert.equal(badJson.status, 'json')
  assert.match(badJson.message, /JSON/)

  const missing = importPresetText(storage, 'ssq', JSON.stringify({ name: '只有名字' }))
  assert.equal(missing.ok, false)
  assert.match(missing.message, /机选条件/)

  const other = importPresetText(storage, 'ssq', JSON.stringify({
    name: '大乐透均衡',
    lottery_type: 'dlt',
    constraints: { odd_min: 2 },
  }))
  assert.equal(other.ok, false)
  assert.match(other.message, /大乐透/)

  const pulse = importPresetText(storage, 'fc3d', JSON.stringify({
    name: '中段',
    strategy: 'pulse',
    constraints: { sum_min: 10 },
  }))
  assert.equal(pulse.ok, false)
  assert.match(pulse.message, /脉动|热号/)
  assert.equal(storage.getItem(PRESET_STORAGE_KEY), null)
})

test('导出的 JSON 可以再导入，损坏的方案库当成没有我的方案', () => {
  const storage = memoryStorage()
  const saved = savePreset(storage, {
    lotteryType: 'pl3',
    name: '中段',
    strategy: 'random',
    constraints: { sum_min: 9, sum_max: 18, odd_min: 1, odd_max: 2 },
  }, { now: () => NOW })
  const text = exportPresetText(saved.preset)
  const parsed = JSON.parse(text)
  assert.equal(parsed.name, '中段')
  assert.equal(parsed.lottery_type, 'pl3')
  assert.equal(parsed.strategy, 'random')
  assert.equal(parsed.id, undefined)

  const other = memoryStorage()
  const imported = importPresetText(other, 'pl3', text)
  assert.equal(imported.ok, true)
  assert.equal(imported.preset.constraints.sum_min, 9)
  assert.equal(imported.preset.strategy, 'random')

  const broken = memoryStorage({ [PRESET_STORAGE_KEY]: '{oops' })
  assert.equal(listPresets(broken, 'ssq').every((item) => item.builtin), true)
  assert.equal(savePreset(broken, {
    lotteryType: 'ssq',
    name: '修复',
    constraints: { span_min: 15 },
  }).ok, true)
})
