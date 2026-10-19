import { constraintStorageKey } from './omitBoard.js'

export const PRESET_STORAGE_KEY = 'yysg.predict.constraintPresets'

export const PRESET_STRATEGIES = ['hot', 'cold', 'hybrid', 'random']

const TYPE_NAMES = {
  ssq: '双色球',
  dlt: '大乐透',
  fc3d: '福彩3D',
  pl3: '排列三',
  pl5: '排列五',
  qxc: '七星彩',
  qlc: '七乐彩',
  kl8: '快乐八',
}

const LIST_FIELDS = ['include_main', 'exclude_main', 'include_special', 'exclude_special']

const NUMBER_FIELDS = [
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
]

const BALL_BUILTINS = {
  ssq: { odd: [3, 3], sum: [80, 130], run: 2 },
  dlt: { odd: [2, 3], sum: [60, 120], run: 2 },
  qlc: { odd: [3, 4], sum: [80, 140], run: 2 },
  kl8: { odd: [9, 11], sum: [700, 920], run: 4 },
}

const DIGIT_BUILTINS = {
  fc3d: { odd: [1, 2], sum: [9, 18] },
  pl3: { odd: [1, 2], sum: [9, 18] },
  pl5: { odd: [2, 3], sum: [16, 29] },
  qxc: { odd: [3, 3], sum: [20, 34] },
}

let idSeq = 0

function makeId(stamp) {
  idSeq += 1
  const parsed = Date.parse(stamp)
  const base = Number.isNaN(parsed) ? Date.now() : parsed
  return `p${base.toString(36)}${idSeq.toString(36)}`
}

function stampOf(options) {
  return typeof options.now === 'function' ? options.now() : new Date().toISOString()
}

export function blankPanelConstraints() {
  return {
    include_main: [],
    exclude_main: [],
    include_special: [],
    exclude_special: [],
    odd_min: '',
    odd_max: '',
    sum_min: '',
    sum_max: '',
    span_min: '',
    span_max: '',
    max_consecutive: '',
    big_min: '',
    big_max: '',
    zone1: '',
    zone2: '',
    zone3: '',
  }
}

function cleanNumber(value) {
  if (value === '' || value === null || value === undefined || typeof value === 'boolean') return ''
  const number = typeof value === 'number' ? value : Number(String(value).trim())
  if (!Number.isInteger(number)) return ''
  return number
}

export function normalizeConstraints(input) {
  const next = blankPanelConstraints()
  if (!input || typeof input !== 'object' || Array.isArray(input)) return next
  for (const key of LIST_FIELDS) {
    if (!Array.isArray(input[key])) continue
    next[key] = input[key].map((item) => String(item).trim()).filter(Boolean)
  }
  for (const key of NUMBER_FIELDS) {
    if (input[key] !== undefined) next[key] = cleanNumber(input[key])
  }
  if (next.odd_min === '' && next.odd_max === '' && input.odd_count !== undefined) {
    const count = cleanNumber(input.odd_count)
    if (count !== '') {
      next.odd_min = count
      next.odd_max = count
    }
  }
  if (next.big_min === '' && next.big_max === '' && input.big_count !== undefined) {
    const count = cleanNumber(input.big_count)
    if (count !== '') {
      next.big_min = count
      next.big_max = count
    }
  }
  if (Array.isArray(input.zone_counts)) {
    const zones = ['zone1', 'zone2', 'zone3']
    input.zone_counts.slice(0, 3).forEach((value, index) => {
      if (next[zones[index]] === '') next[zones[index]] = cleanNumber(value)
    })
  }
  return next
}

function publicStrategy(value) {
  return PRESET_STRATEGIES.includes(value) ? value : ''
}

function normalizeStrategy(value) {
  if (value == null || String(value).trim() === '') return { ok: true, strategy: '' }
  const text = String(value).trim()
  if (text === 'pulse') {
    return { ok: false, status: 'strategy', message: '方案仅用于热号、冷号、混合或随机' }
  }
  if (!PRESET_STRATEGIES.includes(text)) {
    return { ok: false, status: 'strategy', message: '方案策略只能是热号、冷号、混合或随机' }
  }
  return { ok: true, strategy: text }
}

function builtinRecord(lotteryType, slug, name, constraints) {
  return {
    id: `builtin:${lotteryType}:${slug}`,
    name,
    lottery_type: lotteryType,
    constraints: normalizeConstraints(constraints),
    strategy: '',
    updated_at: null,
    builtin: true,
  }
}

export function builtinPresets(lotteryType) {
  const ball = BALL_BUILTINS[lotteryType]
  if (ball) {
    return [
      builtinRecord(lotteryType, 'balance', '均衡', {
        odd_min: ball.odd[0],
        odd_max: ball.odd[1],
        sum_min: ball.sum[0],
        sum_max: ball.sum[1],
        max_consecutive: ball.run,
      }),
      builtinRecord(lotteryType, 'short-run', '少连号', { max_consecutive: ball.run }),
    ]
  }
  const digit = DIGIT_BUILTINS[lotteryType]
  if (!digit) return []
  return [
    builtinRecord(lotteryType, 'mid', '中段均衡', {
      odd_min: digit.odd[0],
      odd_max: digit.odd[1],
      sum_min: digit.sum[0],
      sum_max: digit.sum[1],
    }),
    builtinRecord(lotteryType, 'odd', '奇偶均衡', {
      odd_min: digit.odd[0],
      odd_max: digit.odd[1],
    }),
  ]
}

function isBuiltinId(id) {
  return String(id || '').startsWith('builtin:')
}

function readStore(storage) {
  try {
    const raw = storage.getItem(PRESET_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed
  } catch {
    return {}
  }
}

function writeStore(storage, store) {
  storage.setItem(PRESET_STORAGE_KEY, JSON.stringify(store))
}

function isRecord(item) {
  return Boolean(item) && typeof item === 'object' && typeof item.id === 'string' && typeof item.name === 'string'
}

function toUserPreset(record) {
  return {
    id: record.id,
    name: record.name,
    lottery_type: record.lottery_type,
    constraints: normalizeConstraints(record.constraints),
    strategy: publicStrategy(record.strategy),
    updated_at: record.updated_at || null,
    builtin: false,
  }
}

function userRecords(storage, lotteryType) {
  const list = readStore(storage)[lotteryType]
  if (!Array.isArray(list)) return []
  return list.filter(isRecord)
}

export function listPresets(storage, lotteryType) {
  const mine = userRecords(storage, lotteryType)
    .map(toUserPreset)
    .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))
  return [...builtinPresets(lotteryType), ...mine]
}

export function savePreset(storage, input = {}, options = {}) {
  const lotteryType = String(input.lotteryType || input.lottery_type || '').trim()
  if (!TYPE_NAMES[lotteryType]) return { ok: false, status: 'lottery', message: '未知彩种' }
  const name = String(input.name || '').trim()
  if (!name) return { ok: false, status: 'name', message: '请填写方案名称' }
  if ([...name].length > 24) return { ok: false, status: 'name', message: '方案名称最多 24 个字' }
  const strategy = normalizeStrategy(input.strategy)
  if (!strategy.ok) return strategy
  if (!input.constraints || typeof input.constraints !== 'object' || Array.isArray(input.constraints)) {
    return { ok: false, status: 'constraints', message: '方案缺少机选条件' }
  }
  if (builtinPresets(lotteryType).some((item) => item.name === name)) {
    return { ok: false, status: 'builtin', message: `「${name}」是内置方案，请改名后另存` }
  }
  const constraints = normalizeConstraints(input.constraints)
  const store = readStore(storage)
  const list = userRecords(storage, lotteryType)
  const named = list.find((item) => item.name === name)
  const byId = input.id ? list.find((item) => item.id === input.id) : null
  let target = byId || null
  if (named && (!byId || named.id !== byId.id)) {
    if (!options.overwrite) {
      return {
        ok: false,
        status: 'conflict',
        name,
        message: `已有同名方案「${name}」，要覆盖还是改名？`,
        existingId: named.id,
      }
    }
    target = named
  }
  const updatedAt = stampOf(options)
  const record = {
    id: target ? target.id : makeId(updatedAt),
    name,
    lottery_type: lotteryType,
    constraints,
    strategy: strategy.strategy,
    updated_at: updatedAt,
  }
  store[lotteryType] = target
    ? list.map((item) => (item.id === target.id ? record : item))
    : [...list, record]
  writeStore(storage, store)
  return { ok: true, status: 'saved', preset: toUserPreset(record) }
}

export function renamePreset(storage, lotteryType, id, name, options = {}) {
  if (isBuiltinId(id) || builtinPresets(lotteryType).some((item) => item.id === id)) {
    return { ok: false, status: 'builtin', message: '内置方案不能改名，请另存为我的方案' }
  }
  const trimmed = String(name || '').trim()
  if (!trimmed) return { ok: false, status: 'name', message: '请填写方案名称' }
  if ([...trimmed].length > 24) return { ok: false, status: 'name', message: '方案名称最多 24 个字' }
  if (builtinPresets(lotteryType).some((item) => item.name === trimmed)) {
    return { ok: false, status: 'builtin', message: `「${trimmed}」是内置方案，请换一个名字` }
  }
  const store = readStore(storage)
  const list = userRecords(storage, lotteryType)
  const index = list.findIndex((item) => item.id === id)
  if (index < 0) return { ok: false, status: 'missing', message: '找不到这个方案' }
  const clash = list.find((item) => item.name === trimmed && item.id !== id)
  if (clash) {
    return {
      ok: false,
      status: 'conflict',
      name: trimmed,
      message: `已有同名方案「${trimmed}」，请换一个名字`,
      existingId: clash.id,
    }
  }
  const record = { ...list[index], name: trimmed, updated_at: stampOf(options) }
  const next = [...list]
  next[index] = record
  store[lotteryType] = next
  writeStore(storage, store)
  return { ok: true, status: 'renamed', preset: toUserPreset(record) }
}

export function deletePreset(storage, lotteryType, id) {
  if (isBuiltinId(id) || builtinPresets(lotteryType).some((item) => item.id === id)) {
    return { ok: false, status: 'builtin', message: '内置方案不能删除' }
  }
  const store = readStore(storage)
  const list = userRecords(storage, lotteryType)
  const next = list.filter((item) => item.id !== id)
  if (next.length === list.length) return { ok: false, status: 'missing', message: '找不到这个方案' }
  store[lotteryType] = next
  writeStore(storage, store)
  return { ok: true, status: 'deleted' }
}

export function applyPreset(storage, preset) {
  if (!preset || typeof preset !== 'object') {
    return { ok: false, status: 'missing', message: '找不到这个方案' }
  }
  const lotteryType = String(preset.lottery_type || '')
  if (!TYPE_NAMES[lotteryType]) return { ok: false, status: 'lottery', message: '未知彩种' }
  const constraints = normalizeConstraints(preset.constraints)
  storage.setItem(constraintStorageKey(lotteryType), JSON.stringify(constraints))
  return {
    ok: true,
    constraints,
    strategy: publicStrategy(preset.strategy),
    lottery_type: lotteryType,
  }
}

export function exportPresetText(preset) {
  return JSON.stringify({
    name: preset?.name || '',
    lottery_type: preset?.lottery_type || '',
    strategy: publicStrategy(preset?.strategy),
    constraints: normalizeConstraints(preset?.constraints),
  }, null, 2)
}

function unwrapImport(value) {
  if (Array.isArray(value)) {
    if (value.length === 1 && value[0] && typeof value[0] === 'object' && !Array.isArray(value[0])) return value[0]
    return { error: '请一次粘贴一个方案' }
  }
  if (!value || typeof value !== 'object') return { error: '认不出方案格式，请粘贴单个方案 JSON' }
  if (value.preset && typeof value.preset === 'object' && !Array.isArray(value.preset)) return value.preset
  if (Array.isArray(value.presets)) {
    if (value.presets.length === 1) return value.presets[0]
    return { error: '请一次粘贴一个方案' }
  }
  return value
}

export function importPresetText(storage, lotteryType, text, options = {}) {
  const raw = String(text ?? '').trim()
  if (!raw) return { ok: false, status: 'json', message: '方案内容不是合法的 JSON' }
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { ok: false, status: 'json', message: '方案内容不是合法的 JSON' }
  }
  const item = unwrapImport(parsed)
  if (item?.error) return { ok: false, status: 'shape', message: item.error }
  if (!item.constraints || typeof item.constraints !== 'object' || Array.isArray(item.constraints)) {
    return { ok: false, status: 'constraints', message: '方案缺少机选条件' }
  }
  if (item.lottery_type && item.lottery_type !== lotteryType) {
    const name = TYPE_NAMES[item.lottery_type] || item.lottery_type
    return { ok: false, status: 'lottery', message: `这是${name}的方案，不能导入到当前彩种` }
  }
  if (!String(item.name || '').trim()) return { ok: false, status: 'name', message: '方案缺少名称' }
  return savePreset(storage, {
    lotteryType,
    name: item.name,
    constraints: item.constraints,
    strategy: item.strategy,
  }, options)
}
