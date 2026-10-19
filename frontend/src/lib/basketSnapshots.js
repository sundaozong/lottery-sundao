import {
  addManyToBasket,
  basketProfile,
  itemsForLottery,
  normalizeNumbers,
  numberSignature,
} from './basket.js'

export const SNAPSHOT_STORAGE_KEY = 'yysg.pick.basket.snapshots'

export const SNAPSHOT_DISCLAIMER = '选号篮方案快照只是本地备份，仅供娱乐，不构成投注建议。'

const NAME_LIMIT = 24
const NOTE_LIMIT = 80

let idSeq = 0

function makeId(stamp) {
  idSeq += 1
  const parsed = Date.parse(stamp)
  const base = Number.isNaN(parsed) ? Date.now() : parsed
  return `s${base.toString(36)}${idSeq.toString(36)}`
}

function stampOf(options) {
  return typeof options.now === 'function' ? options.now() : new Date().toISOString()
}

function lotteryName(lotteryType) {
  return basketProfile(lotteryType)?.name || ''
}

function readStore(storage) {
  try {
    const raw = storage.getItem(SNAPSHOT_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed
  } catch {
    return {}
  }
}

function writeStore(storage, store) {
  storage.setItem(SNAPSHOT_STORAGE_KEY, JSON.stringify(store))
}

function isRecord(item) {
  return Boolean(item)
    && typeof item === 'object'
    && typeof item.id === 'string'
    && typeof item.name === 'string'
    && Array.isArray(item.items)
}

function cleanNote(value) {
  return String(value || '').trim().slice(0, NOTE_LIMIT)
}

function copyItems(lotteryType, items) {
  const seen = new Set()
  const copied = []
  for (const item of itemsForLottery(Array.isArray(items) ? items : [], lotteryType)) {
    const parsed = normalizeNumbers(lotteryType, item?.numbers)
    if (!parsed.ok) continue
    const signature = numberSignature(lotteryType, parsed.numbers)
    if (!signature || seen.has(signature)) continue
    seen.add(signature)
    copied.push({
      id: typeof item.id === 'string' && item.id.trim() ? item.id : makeId(),
      lottery_type: lotteryType,
      numbers: parsed.numbers,
      source: item.source || 'manual',
      strategy: item.strategy || '',
      note: item.note || '',
      added_at: item.added_at || '',
    })
  }
  return copied
}

function toPublic(record) {
  return {
    id: record.id,
    name: record.name,
    lottery_type: record.lottery_type,
    items: record.items.map((item) => ({
      id: item.id,
      lottery_type: item.lottery_type,
      numbers: {
        main: [...(item.numbers?.main || [])],
        special: [...(item.numbers?.special || [])],
      },
      source: item.source || '',
      strategy: item.strategy || '',
      note: item.note || '',
      added_at: item.added_at || '',
    })),
    saved_at: record.saved_at || null,
    note: record.note || '',
  }
}

function records(storage, lotteryType) {
  const list = readStore(storage)[lotteryType]
  if (!Array.isArray(list)) return []
  return list.filter(isRecord).map(toPublic)
}

function checkName(name) {
  const trimmed = String(name || '').trim()
  if (!trimmed) return { ok: false, status: 'name', message: '请填写快照名称' }
  if ([...trimmed].length > NAME_LIMIT) return { ok: false, status: 'name', message: '快照名称最多 24 个字' }
  return { ok: true, name: trimmed }
}

export function listSnapshots(storage, lotteryType) {
  return records(storage, lotteryType)
    .sort((a, b) => String(b.saved_at).localeCompare(String(a.saved_at)))
}

export function saveSnapshot(storage, input = {}, options = {}) {
  const lotteryType = String(input.lotteryType || input.lottery_type || '').trim()
  if (!lotteryName(lotteryType)) return { ok: false, status: 'lottery', message: '未知彩种' }
  const name = checkName(input.name)
  if (!name.ok) return name
  const items = copyItems(lotteryType, input.items)
  if (!items.length) {
    return { ok: false, status: 'empty', message: '当前彩种选号篮是空的，先放进号码再保存' }
  }
  const store = readStore(storage)
  const list = records(storage, lotteryType)
  const named = list.find((item) => item.name === name.name)
  if (named && !options.overwrite) {
    return {
      ok: false,
      status: 'conflict',
      name: name.name,
      message: `已有同名快照「${name.name}」，要覆盖还是改名？`,
      existingId: named.id,
    }
  }
  const savedAt = stampOf(options)
  const record = {
    id: named && options.overwrite ? named.id : makeId(savedAt),
    name: name.name,
    lottery_type: lotteryType,
    items,
    saved_at: savedAt,
    note: cleanNote(input.note),
  }
  store[lotteryType] = named && options.overwrite
    ? list.map((item) => (item.id === named.id ? record : item))
    : [...list, record]
  writeStore(storage, store)
  return { ok: true, status: 'saved', snapshot: toPublic(record) }
}

export function renameSnapshot(storage, lotteryType, id, name, options = {}) {
  if (!lotteryName(lotteryType)) return { ok: false, status: 'lottery', message: '未知彩种' }
  const nextName = checkName(name)
  if (!nextName.ok) return nextName
  const store = readStore(storage)
  const list = records(storage, lotteryType)
  const index = list.findIndex((item) => item.id === id)
  if (index < 0) return { ok: false, status: 'missing', message: '找不到这个快照' }
  const clash = list.find((item) => item.name === nextName.name && item.id !== id)
  if (clash) {
    return {
      ok: false,
      status: 'conflict',
      name: nextName.name,
      message: `已有同名快照「${nextName.name}」，请换一个名字`,
      existingId: clash.id,
    }
  }
  const record = { ...list[index], name: nextName.name, saved_at: stampOf(options) }
  const next = [...list]
  next[index] = record
  store[lotteryType] = next
  writeStore(storage, store)
  return { ok: true, status: 'renamed', snapshot: toPublic(record) }
}

export function deleteSnapshot(storage, lotteryType, id) {
  if (!lotteryName(lotteryType)) return { ok: false, status: 'lottery', message: '未知彩种' }
  const store = readStore(storage)
  const list = records(storage, lotteryType)
  const next = list.filter((item) => item.id !== id)
  if (next.length === list.length) return { ok: false, status: 'missing', message: '找不到这个快照' }
  store[lotteryType] = next
  writeStore(storage, store)
  return { ok: true, status: 'deleted' }
}

export function applySnapshot(basketItems, snapshot) {
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
    return { ok: false, status: 'missing', message: '找不到这个快照' }
  }
  const lotteryType = String(snapshot.lottery_type || '').trim()
  const profile = basketProfile(lotteryType)
  if (!profile) return { ok: false, status: 'lottery', message: '未知彩种' }
  const copied = copyItems(lotteryType, snapshot.items)
  if (!copied.length) return { ok: false, status: 'empty', message: '这张快照里没有可用的注' }
  const kept = (basketItems || []).filter((item) => item.lottery_type !== lotteryType)
  const used = new Set(kept.map((item) => item.id))
  const drafts = []
  const ids = []
  for (const item of copied) {
    drafts.push({
      lottery_type: lotteryType,
      numbers: item.numbers,
      source: item.source,
      strategy: item.strategy,
      note: item.note,
    })
    const id = item.id && !used.has(item.id) ? item.id : undefined
    if (id) used.add(id)
    ids.push(id)
  }
  const result = addManyToBasket(kept, drafts, { ids })
  const addedAt = new Map(copied.map((item) => [item.id, item.added_at]))
  const items = result.items.map((item) => {
    if (item.lottery_type !== lotteryType) return item
    const stamp = addedAt.get(item.id)
    return stamp ? { ...item, added_at: stamp } : item
  })
  const label = snapshot.name ? `「${snapshot.name}」` : '这张快照'
  return {
    ok: true,
    status: 'applied',
    items,
    added: result.added,
    message: `已用快照${label}替换${profile.name} ${result.added} 注，其他彩种未改`,
  }
}

export function exportSnapshotsText(storage, lotteryType) {
  return JSON.stringify({
    kind: 'basket-snapshots',
    lottery_type: lotteryType,
    snapshots: listSnapshots(storage, lotteryType),
  }, null, 2)
}

function unwrapImport(value) {
  if (Array.isArray(value)) return { snapshots: value, lottery_type: '' }
  if (!value || typeof value !== 'object') {
    return { error: '认不出快照格式，请粘贴方案快照 JSON', status: 'shape' }
  }
  if (Array.isArray(value.snapshots)) {
    return { snapshots: value.snapshots, lottery_type: String(value.lottery_type || '') }
  }
  if (Array.isArray(value.items) && (value.name || value.lottery_type)) {
    return { snapshots: [value], lottery_type: String(value.lottery_type || '') }
  }
  return { error: '认不出快照格式，请粘贴方案快照 JSON', status: 'shape' }
}

export function importSnapshotsText(storage, lotteryType, text, options = {}) {
  if (!lotteryName(lotteryType)) return { ok: false, status: 'lottery', message: '未知彩种' }
  const raw = String(text ?? '').trim()
  if (!raw) return { ok: false, status: 'json', message: '快照内容不是合法的 JSON' }
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { ok: false, status: 'json', message: '快照内容不是合法的 JSON' }
  }
  const unwrapped = unwrapImport(parsed)
  if (unwrapped.error) return { ok: false, status: unwrapped.status || 'shape', message: unwrapped.error }
  const matching = []
  let foreignType = ''
  for (const item of unwrapped.snapshots) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue
    const type = String(item.lottery_type || unwrapped.lottery_type || '').trim()
    if (type && type !== lotteryType) {
      foreignType = foreignType || type
      continue
    }
    matching.push(item)
  }
  if (!matching.length) {
    if (foreignType) {
      const name = lotteryName(foreignType) || foreignType
      return { ok: false, status: 'lottery', message: `这是${name}的快照，不能导入到当前彩种` }
    }
    return { ok: false, status: 'empty', message: '没有可导入的快照' }
  }
  const store = readStore(storage)
  const list = records(storage, lotteryType)
  const seenIds = new Set(list.map((item) => item.id))
  const seenNames = new Set(list.map((item) => item.name))
  const next = [...list]
  let added = 0
  let skipped = 0
  for (const item of matching) {
    const name = checkName(item.name)
    const copied = copyItems(lotteryType, item.items)
    const id = String(item.id || '').trim()
    if (!name.ok || !copied.length || (id && seenIds.has(id)) || (name.ok && seenNames.has(name.name))) {
      skipped += 1
      continue
    }
    const savedAt = typeof item.saved_at === 'string' && item.saved_at ? item.saved_at : stampOf(options)
    const record = {
      id: id || makeId(savedAt),
      name: name.name,
      lottery_type: lotteryType,
      items: copied,
      saved_at: savedAt,
      note: cleanNote(item.note),
    }
    next.push(record)
    seenIds.add(record.id)
    seenNames.add(record.name)
    added += 1
  }
  store[lotteryType] = next
  writeStore(storage, store)
  return {
    ok: true,
    status: 'imported',
    added,
    skipped,
    snapshots: listSnapshots(storage, lotteryType),
  }
}
