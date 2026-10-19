import assert from 'node:assert/strict'
import test from 'node:test'

import { BASKET_STORAGE_KEY, addToBasket, itemsForLottery, numberSignature } from './basket.js'
import {
  SNAPSHOT_STORAGE_KEY,
  applySnapshot,
  deleteSnapshot,
  exportSnapshotsText,
  importSnapshotsText,
  listSnapshots,
  renameSnapshot,
  saveSnapshot,
} from './basketSnapshots.js'

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

function ssq(main, special = ['07'], extra = {}) {
  return {
    id: extra.id || 'ssq-1',
    lottery_type: 'ssq',
    numbers: { main, special },
    source: extra.source || 'manual',
    strategy: extra.strategy || '',
    note: extra.note || '',
    added_at: extra.added_at || NOW,
  }
}

function dlt(id = 'dlt-1') {
  return {
    id,
    lottery_type: 'dlt',
    numbers: { main: ['01', '02', '03', '04', '05'], special: ['01', '02'] },
    source: 'predict',
    strategy: 'cold',
    note: '后区',
    added_at: NOW,
  }
}

test('保存当前彩种篮内容，空篮拒绝，且不改选号篮存储', () => {
  const storage = memoryStorage({
    [BASKET_STORAGE_KEY]: JSON.stringify([ssq(['01', '02', '03', '04', '05', '06'])]),
  })
  const empty = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '空篮',
    items: [],
  }, { now: () => NOW })
  assert.equal(empty.ok, false)
  assert.equal(empty.status, 'empty')
  assert.match(empty.message, /空/)
  assert.equal(storage.getItem(SNAPSHOT_STORAGE_KEY), null)
  assert.equal(JSON.parse(storage.getItem(BASKET_STORAGE_KEY)).length, 1)

  const otherOnly = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '只有大乐透',
    items: [dlt()],
  })
  assert.equal(otherOnly.ok, false)
  assert.equal(otherOnly.status, 'empty')

  const saved = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    note: '  先留着  ',
    items: [
      ssq(['1', '8', '9', '16', '23', '33'], ['7'], { id: 'a', source: 'predict', strategy: 'hot', note: '胆' }),
      ssq(['33', '01', '08', '09', '16', '23'], ['07'], { id: 'dup' }),
      ssq(['02', '03', '04', '05', '06', '07'], ['08'], { id: 'b', source: 'paste' }),
    ],
  }, { now: () => NOW })
  assert.equal(saved.ok, true)
  assert.equal(saved.status, 'saved')
  assert.equal(saved.snapshot.name, '周末')
  assert.equal(saved.snapshot.lottery_type, 'ssq')
  assert.equal(saved.snapshot.saved_at, NOW)
  assert.equal(saved.snapshot.note, '先留着')
  assert.equal(saved.snapshot.items.length, 2)
  assert.deepEqual(saved.snapshot.items[0].numbers.main, ['01', '08', '09', '16', '23', '33'])
  assert.deepEqual(saved.snapshot.items[0].numbers.special, ['07'])
  assert.equal(saved.snapshot.items[0].source, 'predict')
  assert.equal(saved.snapshot.items[0].strategy, 'hot')
  assert.equal(saved.snapshot.items[0].note, '胆')
  assert.equal(saved.snapshot.items[0].id, 'a')
  assert.equal(
    numberSignature('ssq', saved.snapshot.items[0].numbers),
    numberSignature('ssq', { main: ['33', '1', '8', '9', '16', '23'], special: ['7'] }),
  )
  assert.equal(storage.getItem(BASKET_STORAGE_KEY), JSON.stringify([ssq(['01', '02', '03', '04', '05', '06'])]))

  const listed = listSnapshots(storage, 'ssq')
  assert.equal(listed.length, 1)
  assert.equal(listed[0].id, saved.snapshot.id)
  assert.equal(listed[0].items.length, 2)
})

test('同名默认不覆盖，确认后更新原快照并保留 id', () => {
  const storage = memoryStorage()
  const first = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    items: [ssq(['01', '02', '03', '04', '05', '06'], ['01'], { id: 'a' })],
  }, { now: () => NOW })
  assert.equal(first.ok, true)

  const conflict = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    items: [ssq(['02', '03', '04', '05', '06', '07'], ['02'], { id: 'b' })],
  }, { now: () => LATER })
  assert.equal(conflict.ok, false)
  assert.equal(conflict.status, 'conflict')
  assert.match(conflict.message, /覆盖/)
  assert.equal(conflict.existingId, first.snapshot.id)
  assert.equal(listSnapshots(storage, 'ssq')[0].items[0].id, 'a')

  const overwritten = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    note: '改过',
    items: [ssq(['02', '03', '04', '05', '06', '07'], ['02'], { id: 'b', source: 'manual' })],
  }, { overwrite: true, now: () => LATER })
  assert.equal(overwritten.ok, true)
  assert.equal(overwritten.snapshot.id, first.snapshot.id)
  assert.equal(overwritten.snapshot.saved_at, LATER)
  assert.equal(overwritten.snapshot.note, '改过')
  assert.equal(overwritten.snapshot.items.length, 1)
  assert.equal(overwritten.snapshot.items[0].id, 'b')
  assert.equal(listSnapshots(storage, 'ssq').length, 1)
})

test('快照按彩种隔离，别的彩种可以用同名', () => {
  const storage = memoryStorage()
  assert.equal(saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    items: [ssq(['01', '02', '03', '04', '05', '06'])],
  }, { now: () => NOW }).ok, true)
  assert.equal(saveSnapshot(storage, {
    lotteryType: 'dlt',
    name: '周末',
    items: [dlt()],
  }, { now: () => LATER }).ok, true)

  const ssqList = listSnapshots(storage, 'ssq')
  const dltList = listSnapshots(storage, 'dlt')
  assert.equal(ssqList.length, 1)
  assert.equal(dltList.length, 1)
  assert.equal(ssqList[0].lottery_type, 'ssq')
  assert.equal(dltList[0].lottery_type, 'dlt')
  assert.equal(dltList[0].items[0].lottery_type, 'dlt')
  assert.notEqual(ssqList[0].id, dltList[0].id)
  assert.equal(deleteSnapshot(storage, 'dlt', dltList[0].id).ok, true)
  assert.equal(listSnapshots(storage, 'ssq').length, 1)
  assert.equal(listSnapshots(storage, 'dlt').length, 0)
})

test('套用只替换该彩种，号码经 normalize 与 numberSignature 对齐', () => {
  const kept = addToBasket([], {
    lottery_type: 'dlt',
    numbers: { main: ['03', '11', '19', '27', '35'], special: ['04', '09'] },
    source: 'manual',
    note: '别动',
  }, { now: NOW, id: 'keep-dlt' }).items
  const basket = addToBasket(kept, {
    lottery_type: 'ssq',
    numbers: { main: ['01', '02', '03', '04', '05', '06'], special: ['01'] },
    source: 'manual',
  }, { now: NOW, id: 'old-ssq' }).items

  const storage = memoryStorage()
  const saved = saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    items: [
      ssq(['9', '1', '8', '16', '23', '33'], ['7'], { id: 'new-ssq', source: 'predict', strategy: 'hybrid', note: '回放', added_at: '2026-10-18T08:00:00.000Z' }),
      { id: 'bad', lottery_type: 'ssq', numbers: { main: ['01'], special: ['01'] }, source: 'manual' },
    ],
  }, { now: () => NOW })
  const applied = applySnapshot(basket, saved.snapshot)
  assert.equal(applied.ok, true)
  assert.equal(applied.status, 'applied')
  assert.equal(itemsForLottery(applied.items, 'dlt').length, 1)
  assert.equal(itemsForLottery(applied.items, 'dlt')[0].id, 'keep-dlt')
  assert.equal(itemsForLottery(applied.items, 'dlt')[0].note, '别动')
  const ssqItems = itemsForLottery(applied.items, 'ssq')
  assert.equal(ssqItems.length, 1)
  assert.equal(ssqItems[0].id, 'new-ssq')
  assert.equal(ssqItems[0].source, 'predict')
  assert.equal(ssqItems[0].strategy, 'hybrid')
  assert.equal(ssqItems[0].note, '回放')
  assert.equal(ssqItems[0].added_at, '2026-10-18T08:00:00.000Z')
  assert.deepEqual(ssqItems[0].numbers.main, ['01', '08', '09', '16', '23', '33'])
  assert.equal(itemsForLottery(basket, 'ssq')[0].id, 'old-ssq')
  assert.equal(listSnapshots(storage, 'ssq')[0].items.length, 1)

  const cleared = applySnapshot(applied.items, { ...saved.snapshot, items: [] })
  assert.equal(cleared.ok, false)
  assert.equal(cleared.status, 'empty')
  assert.equal(itemsForLottery(applied.items, 'ssq').length, 1)
})

test('改名和删除，缺名称、重名和找不到时给出提示', () => {
  const storage = memoryStorage()
  const weekend = saveSnapshot(storage, {
    lotteryType: 'fc3d',
    name: '周末',
    items: [{
      id: 'f1',
      lottery_type: 'fc3d',
      numbers: { main: ['1', '2', '3'], special: [] },
      source: 'manual',
      strategy: '',
      note: '',
      added_at: NOW,
    }],
  }, { now: () => NOW })
  const work = saveSnapshot(storage, {
    lotteryType: 'fc3d',
    name: '工作日',
    items: [{
      id: 'f2',
      lottery_type: 'fc3d',
      numbers: { main: ['3', '2', '1'], special: [] },
      source: 'form',
    }],
  }, { now: () => LATER })
  assert.equal(weekend.ok, true)
  assert.equal(work.ok, true)
  assert.deepEqual(listSnapshots(storage, 'fc3d').map((item) => item.name), ['工作日', '周末'])

  const blank = renameSnapshot(storage, 'fc3d', weekend.snapshot.id, '   ')
  assert.equal(blank.ok, false)
  assert.equal(blank.status, 'name')

  const clash = renameSnapshot(storage, 'fc3d', weekend.snapshot.id, '工作日')
  assert.equal(clash.ok, false)
  assert.equal(clash.status, 'conflict')
  assert.match(clash.message, /换一个名字/)

  const renamed = renameSnapshot(storage, 'fc3d', weekend.snapshot.id, '夜场', { now: () => '2026-10-19T03:00:00.000Z' })
  assert.equal(renamed.ok, true)
  assert.equal(renamed.snapshot.name, '夜场')
  assert.equal(renamed.snapshot.items[0].numbers.main.join(''), '123')
  assert.equal(renamed.snapshot.saved_at, '2026-10-19T03:00:00.000Z')

  const missing = deleteSnapshot(storage, 'fc3d', 'nope')
  assert.equal(missing.ok, false)
  assert.equal(missing.status, 'missing')
  const removed = deleteSnapshot(storage, 'fc3d', work.snapshot.id)
  assert.equal(removed.ok, true)
  assert.deepEqual(listSnapshots(storage, 'fc3d').map((item) => item.name), ['夜场'])
})

test('导出当前彩种全部快照，导入合并并按 id 去重，非法 JSON 友好报错', () => {
  const storage = memoryStorage()
  saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '周末',
    items: [ssq(['01', '02', '03', '04', '05', '06'], ['01'], { id: 'a' })],
  }, { now: () => NOW })
  saveSnapshot(storage, {
    lotteryType: 'ssq',
    name: '工作日',
    items: [ssq(['02', '03', '04', '05', '06', '07'], ['02'], { id: 'b' })],
  }, { now: () => LATER })
  saveSnapshot(storage, {
    lotteryType: 'dlt',
    name: '别的',
    items: [dlt()],
  }, { now: () => NOW })

  const text = exportSnapshotsText(storage, 'ssq')
  const parsed = JSON.parse(text)
  assert.equal(parsed.lottery_type, 'ssq')
  assert.equal(parsed.snapshots.length, 2)
  assert.equal(parsed.snapshots.some((item) => item.lottery_type !== 'ssq'), false)
  assert.equal(parsed.snapshots.some((item) => item.name === '别的'), false)

  const bad = importSnapshotsText(storage, 'ssq', '{oops')
  assert.equal(bad.ok, false)
  assert.equal(bad.status, 'json')
  assert.match(bad.message, /JSON/)
  assert.equal(listSnapshots(storage, 'ssq').length, 2)

  const other = memoryStorage()
  const imported = importSnapshotsText(other, 'ssq', text, { now: () => LATER })
  assert.equal(imported.ok, true)
  assert.equal(imported.added, 2)
  assert.equal(imported.skipped, 0)
  assert.equal(listSnapshots(other, 'ssq').length, 2)
  assert.equal(listSnapshots(other, 'dlt').length, 0)

  const again = importSnapshotsText(other, 'ssq', JSON.stringify({
    lottery_type: 'ssq',
    snapshots: [
      {
        id: listSnapshots(other, 'ssq').find((item) => item.name === '周末').id,
        name: '周末改名',
        lottery_type: 'ssq',
        items: [ssq(['03', '04', '05', '06', '07', '08'], ['03'], { id: 'z' })],
      },
      {
        id: 'fresh',
        name: '夜场',
        lottery_type: 'ssq',
        items: [ssq(['04', '05', '06', '07', '08', '09'], ['04'], { id: 'c' })],
      },
      {
        id: 'fresh',
        name: '夜场副本',
        lottery_type: 'ssq',
        items: [ssq(['05', '06', '07', '08', '09', '10'], ['05'], { id: 'd' })],
      },
      {
        id: 'name-clash',
        name: '工作日',
        lottery_type: 'ssq',
        items: [ssq(['06', '07', '08', '09', '10', '11'], ['06'], { id: 'e' })],
      },
      {
        id: 'dlt-snap',
        name: '大乐透',
        lottery_type: 'dlt',
        items: [dlt('dlt-x')],
      },
    ],
  }))
  assert.equal(again.ok, true)
  assert.equal(again.added, 1)
  assert.equal(again.skipped, 3)
  const names = listSnapshots(other, 'ssq').map((item) => item.name).sort()
  assert.deepEqual(names, ['周末', '夜场', '工作日'])
  assert.equal(listSnapshots(other, 'ssq').find((item) => item.name === '周末').items[0].id, 'a')
  assert.equal(listSnapshots(other, 'dlt').length, 0)
  assert.equal(other.getItem(BASKET_STORAGE_KEY), null)

  const wrong = importSnapshotsText(other, 'ssq', JSON.stringify({
    lottery_type: 'dlt',
    snapshots: [{ id: 'only-dlt', name: '大乐透', lottery_type: 'dlt', items: [dlt('dlt-y')] }],
  }))
  assert.equal(wrong.ok, false)
  assert.equal(wrong.status, 'lottery')
  assert.match(wrong.message, /大乐透/)
})

test('损坏的快照库当成没有快照，保存仍可写回', () => {
  const broken = memoryStorage({ [SNAPSHOT_STORAGE_KEY]: '{oops' })
  assert.deepEqual(listSnapshots(broken, 'ssq'), [])
  const saved = saveSnapshot(broken, {
    lotteryType: 'pl3',
    name: '修复',
    items: [{
      lottery_type: 'pl3',
      numbers: { main: ['0', '9', '1'], special: [] },
      source: 'omit',
    }],
  }, { now: () => NOW })
  assert.equal(saved.ok, true)
  assert.deepEqual(saved.snapshot.items[0].numbers.main, ['0', '9', '1'])
  assert.equal(listSnapshots(broken, 'pl3')[0].name, '修复')
  assert.equal(saveSnapshot(broken, { lotteryType: 'nope', name: 'x', items: [ssq(['01', '02', '03', '04', '05', '06'])] }).status, 'lottery')
  assert.equal(saveSnapshot(broken, { lotteryType: 'pl3', name: '', items: [] }).status, 'name')
})
