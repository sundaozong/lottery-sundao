import assert from 'node:assert/strict'
import test from 'node:test'

import { bandText, meterLayout, stanceClass, tokenize } from './formCheck.js'

test('tokenize splits spaces and commas', () => {
  assert.deepEqual(tokenize('01, 02，03  04'), ['01', '02', '03', '04'])
  assert.deepEqual(tokenize(''), [])
  assert.deepEqual(tokenize(null), [])
})

test('bandText names the compared scalar', () => {
  assert.equal(bandText({ band_low: 2, band_high: 4, band_label: '2–4', compared: '偏度' }), '常见带 偏度 2–4')
  assert.equal(bandText({ band_low: 21, band_high: 39, band_label: '21–39', compared: '' }), '常见带 21–39')
  assert.equal(bandText({ band_low: null, band_high: null }), '暂无常见带')
  assert.equal(bandText(null), '暂无常见带')
})

test('stanceClass stays on the calm badges', () => {
  assert.equal(stanceClass('high'), 'badge-warn')
  assert.equal(stanceClass('low'), 'badge-info')
  assert.equal(stanceClass('center'), 'badge-ok')
  assert.equal(stanceClass('unavailable'), 'badge-muted')
})

test('meterLayout places the common band and the mark', () => {
  const layout = meterLayout({ history_min: 10, history_max: 40, band_low: 17.5, band_high: 32.5, value: 40 })
  assert.equal(layout.bandLeft, 25)
  assert.equal(layout.bandWidth, 50)
  assert.equal(layout.mark, 100)
  assert.equal(meterLayout({ history_min: 8, history_max: 8, band_low: 8, band_high: 8, value: 8 }), null)
  assert.equal(meterLayout({ history_min: null, history_max: null }), null)
})
