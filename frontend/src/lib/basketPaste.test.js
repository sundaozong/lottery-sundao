import assert from 'node:assert/strict'
import test from 'node:test'

import { addManyToBasket, addToBasket, formatBasketText, recordBody, sourceLabel } from './basket.js'
import { parseBasketPaste, previewBasketPaste } from './basketPaste.js'

const NOW = '2026-10-19T08:00:00.000Z'

function ssq(main, special = ['07']) {
  return { main, special }
}

test('导出文本再粘贴能还原双色球和大乐透', () => {
  const items = addManyToBasket([], [
    { lottery_type: 'ssq', numbers: ssq(['1', '8', '9', '16', '23', '33'], ['7']), source: 'manual' },
    { lottery_type: 'dlt', numbers: { main: ['5', '11', '19', '28', '33'], special: ['10', '2'] }, source: 'predict' },
  ], { now: NOW, ids: ['s', 'd'] }).items

  const ssqText = formatBasketText(items, 'ssq')
  const ssqParsed = parseBasketPaste('ssq', ssqText)
  assert.equal(ssqParsed.invalid.length, 0)
  assert.equal(ssqParsed.drafts.length, 1)
  assert.deepEqual(ssqParsed.drafts[0].numbers, { main: ['01', '08', '09', '16', '23', '33'], special: ['07'] })
  assert.equal(ssqParsed.drafts[0].source, 'paste')
  assert.equal(ssqParsed.drafts[0].lottery_type, 'ssq')

  const dltText = formatBasketText(items, 'dlt')
  assert.match(dltText, /05 11 19 28 33 \+ 02 10/)
  const dltParsed = parseBasketPaste('dlt', dltText)
  assert.equal(dltParsed.invalid.length, 0)
  assert.deepEqual(dltParsed.drafts[0].numbers, { main: ['05', '11', '19', '28', '33'], special: ['02', '10'] })
})

test('福彩3D 导出标题含数字，粘贴时不当成号码', () => {
  const items = addToBasket([], {
    lottery_type: 'fc3d',
    numbers: { main: ['1', '2', '3'] },
  }, { now: NOW, id: 'f' }).items
  const text = formatBasketText(items, 'fc3d')
  assert.match(text, /福彩3D/)
  const parsed = parseBasketPaste('fc3d', text)
  assert.equal(parsed.invalid.length, 0)
  assert.equal(parsed.drafts.length, 1)
  assert.deepEqual(parsed.drafts[0].numbers.main, ['1', '2', '3'])
  assert.deepEqual(parsed.drafts[0].numbers.special, [])
})

test('多行混合分隔符、特别号和空行', () => {
  const text = [
    '双色球',
    '',
    '01 02 03 04 05 06 + 07',
    '08,09,10,11,12,13|16',
    '1，2，3，4，5，6 + 9',
    '   ',
    '选号篮仅供娱乐，不构成投注建议。',
  ].join('\r\n')
  const parsed = parseBasketPaste('ssq', text)
  assert.equal(parsed.invalid.length, 0)
  assert.equal(parsed.drafts.length, 3)
  assert.deepEqual(parsed.drafts[0].numbers.special, ['07'])
  assert.deepEqual(parsed.drafts[1].numbers, {
    main: ['08', '09', '10', '11', '12', '13'],
    special: ['16'],
  })
  assert.deepEqual(parsed.drafts[2].numbers, {
    main: ['01', '02', '03', '04', '05', '06'],
    special: ['09'],
  })
  assert.ok(parsed.skipped >= 3)
})

test('没有特别号分隔符时，尾部号码按彩种个数当作特别号', () => {
  const ssqParsed = parseBasketPaste('ssq', '01,02,03,04,05,06,07')
  assert.deepEqual(ssqParsed.drafts[0].numbers, {
    main: ['01', '02', '03', '04', '05', '06'],
    special: ['07'],
  })
  const dltParsed = parseBasketPaste('dlt', '01 02 03 04 05 11 12')
  assert.deepEqual(dltParsed.drafts[0].numbers.special, ['11', '12'])
  const qxcParsed = parseBasketPaste('qxc', '0 1 2 3 4 5 14')
  assert.deepEqual(qxcParsed.drafts[0].numbers.main, ['0', '1', '2', '3', '4', '5'])
  assert.deepEqual(qxcParsed.drafts[0].numbers.special, ['14'])
})

test('数字彩按位保留顺序和重复，乐透按集合拒绝重复', () => {
  const digits = parseBasketPaste('fc3d', '3 2 1\n1 1 2')
  assert.equal(digits.invalid.length, 0)
  assert.deepEqual(digits.drafts[0].numbers.main, ['3', '2', '1'])
  assert.deepEqual(digits.drafts[1].numbers.main, ['1', '1', '2'])

  const same = parseBasketPaste('pl3', '1,2,3')
  assert.deepEqual(same.drafts[0].numbers.main, ['1', '2', '3'])
  const pl5 = parseBasketPaste('pl5', '0 9 8 7 6')
  assert.deepEqual(pl5.drafts[0].numbers.main, ['0', '9', '8', '7', '6'])

  const repeated = parseBasketPaste('ssq', '01 01 02 03 04 05 + 07')
  assert.equal(repeated.drafts.length, 0)
  assert.match(repeated.invalid[0].message, /重复/)
  assert.equal(repeated.invalid[0].line, 1)
})

test('七乐彩、快乐八和七星彩按各自范围校验', () => {
  const qlc = parseBasketPaste('qlc', '1 2 3 4 5 6 7')
  assert.deepEqual(qlc.drafts[0].numbers.main, ['01', '02', '03', '04', '05', '06', '07'])
  assert.deepEqual(qlc.drafts[0].numbers.special, [])

  const extra = parseBasketPaste('qlc', '01 02 03 04 05 06 07 + 08')
  assert.equal(extra.drafts.length, 0)
  assert.match(extra.invalid[0].message, /特别号/)

  const kl8 = parseBasketPaste('kl8', '1 2 3 4 5 6 7 8 9 10 11')
  assert.equal(kl8.drafts[0].numbers.main.length, 11)
  const tooMany = parseBasketPaste('kl8', Array.from({ length: 21 }, (_, i) => String(i + 1)).join(' '))
  assert.equal(tooMany.drafts.length, 0)
  assert.match(tooMany.invalid[0].message, /最多/)

  const qxc = parseBasketPaste('qxc', '0 1 2 3 4 5 + 07\n1|2|3|4|5|6|0')
  assert.deepEqual(qxc.drafts[0].numbers.special, ['7'])
  assert.equal(qxc.drafts.length, 1)
  assert.match(qxc.invalid[0].message, /分隔符/)
  assert.equal(qxc.invalid[0].line, 2)
})

test('无效行给出原因，预览只保留前几条', () => {
  const text = ['1', '99 02 03 04 05 06 + 07', '01 02 03 04 05 + 07', '01 02 03 04 05 06 + 17', '注1'].join('\n')
  const preview = previewBasketPaste([], 'ssq', text)
  assert.equal(preview.added, 0)
  assert.equal(preview.duplicates, 0)
  assert.equal(preview.invalidCount, 5)
  assert.equal(preview.errors.length, 3)
  assert.equal(preview.errors[0].line, 1)
  assert.equal(preview.errors[2].line, 3)
  assert.match(preview.errors[1].message, /范围|不是数字/)
  assert.equal(preview.drafts.length, 0)
})

test('和篮里已有的号码重复时计数，不覆盖', () => {
  const existing = addToBasket([], {
    lottery_type: 'ssq',
    numbers: ssq(['01', '02', '03', '04', '05', '06'], ['07']),
    source: 'manual',
  }, { now: NOW, id: 'old' }).items
  const text = [
    '06 05 04 03 02 01 + 07',
    '01 02 03 04 05 06 + 07',
    '02 03 04 05 06 07 + 08',
  ].join('\n')
  const preview = previewBasketPaste(existing, 'ssq', text)
  assert.equal(preview.added, 1)
  assert.equal(preview.duplicates, 2)
  assert.equal(preview.invalidCount, 0)
  assert.equal(existing.length, 1)
  assert.equal(existing[0].id, 'old')

  const applied = addManyToBasket(existing, preview.drafts, { now: NOW, ids: ['dup1', 'dup2', 'new'] })
  assert.equal(applied.added, 1)
  assert.equal(applied.duplicates, 2)
  assert.equal(applied.items.length, 2)
  assert.equal(applied.items[0].id, 'old')
  assert.equal(applied.items[0].source, 'manual')
  assert.equal(applied.items[1].source, 'paste')
  assert.equal(sourceLabel(applied.items[1]), '粘贴')
  assert.match(recordBody(applied.items[1], { today: '2026-10-19' }).note, /粘贴/)
})

test('空输入和未知彩种不产生可加入的注', () => {
  for (const text of ['', '   \n\t', null, undefined]) {
    const preview = previewBasketPaste([], 'ssq', text)
    assert.equal(preview.added, 0)
    assert.equal(preview.duplicates, 0)
    assert.equal(preview.invalidCount, 0)
    assert.deepEqual(preview.drafts, [])
    assert.deepEqual(preview.errors, [])
  }
  const unknown = parseBasketPaste('nope', '1 2 3')
  assert.equal(unknown.drafts.length, 0)
  assert.match(unknown.invalid[0].message, /未知彩种/)
  const blankUnknown = previewBasketPaste([], 'nope', '  ')
  assert.equal(blankUnknown.invalidCount, 0)
  assert.deepEqual(blankUnknown.drafts, [])
})
