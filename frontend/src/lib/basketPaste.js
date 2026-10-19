import { BASKET_DISCLAIMER, addManyToBasket, basketProfile, normalizeNumbers } from './basket.js'

const ERROR_PREVIEW_LIMIT = 3

function clip(text) {
  const clean = String(text || '').replace(/\s+/g, ' ').trim()
  if (clean.length <= 48) return clean
  return `${clean.slice(0, 48)}…`
}

function tokenize(text) {
  return String(text || '').trim().split(/[\s,，]+/).filter(Boolean)
}

function countChar(text, char) {
  return text.split(char).length - 1
}

function isSkippable(line, profile) {
  if (!line) return true
  if (line === profile.name) return true
  if (line === BASKET_DISCLAIMER) return true
  return !/\d/.test(line)
}

function splitLine(line, profile) {
  const plus = countChar(line, '+')
  const pipe = countChar(line, '|')
  if (plus && pipe) return { ok: false, message: '主号和特别号只用一种分隔符' }
  if (plus > 1 || pipe > 1) return { ok: false, message: '特别号分隔符只能出现一次' }
  let mainText = line
  let specialText = ''
  if (plus === 1 || pipe === 1) {
    const parts = line.split(plus === 1 ? '+' : '|')
    mainText = parts[0]
    specialText = parts[1]
  }
  let main = tokenize(mainText)
  let special = tokenize(specialText)
  const expected = (profile.mainCount || 0) + (profile.specCount || 0)
  if (!special.length && profile.specCount && profile.mainCount && main.length === expected) {
    special = main.slice(profile.mainCount)
    main = main.slice(0, profile.mainCount)
  }
  return { ok: true, main, special }
}

export function parseBasketPaste(lotteryType, text) {
  const profile = basketProfile(lotteryType)
  const raw = text == null ? '' : String(text)
  if (!profile) {
    return {
      drafts: [],
      invalid: raw.trim() ? [{ line: 1, text: clip(raw), message: '未知彩种' }] : [],
      skipped: 0,
    }
  }
  const drafts = []
  const invalid = []
  let skipped = 0
  raw.split(/\r?\n/).forEach((row, index) => {
    const line = row.trim()
    if (isSkippable(line, profile)) {
      skipped += 1
      return
    }
    const split = splitLine(line, profile)
    if (!split.ok) {
      invalid.push({ line: index + 1, text: clip(line), message: split.message })
      return
    }
    const parsed = normalizeNumbers(lotteryType, { main: split.main, special: split.special })
    if (!parsed.ok) {
      invalid.push({ line: index + 1, text: clip(line), message: parsed.message })
      return
    }
    drafts.push({
      lottery_type: lotteryType,
      numbers: parsed.numbers,
      source: 'paste',
    })
  })
  return { drafts, invalid, skipped }
}

export function previewBasketPaste(items, lotteryType, text) {
  const parsed = parseBasketPaste(lotteryType, text)
  const applied = addManyToBasket(items || [], parsed.drafts)
  return {
    drafts: parsed.drafts,
    added: applied.added,
    duplicates: applied.duplicates,
    invalidCount: parsed.invalid.length,
    errors: parsed.invalid.slice(0, ERROR_PREVIEW_LIMIT),
    skipped: parsed.skipped,
  }
}
