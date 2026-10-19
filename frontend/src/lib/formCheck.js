export function tokenize(value) {
  return String(value ?? '').trim().split(/[\s,，]+/).filter(Boolean)
}

export function bandText(metric) {
  if (!metric || metric.band_low == null || metric.band_high == null) return '暂无常见带'
  const name = metric.compared ? `${metric.compared} ` : ''
  const range = metric.band_label || `${metric.band_low}–${metric.band_high}`
  return `常见带 ${name}${range}`
}

export function stanceClass(stance) {
  if (stance === 'high') return 'badge-warn'
  if (stance === 'low') return 'badge-info'
  if (stance === 'center') return 'badge-ok'
  return 'badge-muted'
}

export function meterLayout(metric) {
  if (!metric || metric.history_min == null || metric.history_max == null) return null
  const min = Number(metric.history_min)
  const max = Number(metric.history_max)
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return null
  const span = max - min
  const clamp = (raw) => {
    const value = Number(raw)
    if (!Number.isFinite(value)) return 0
    return Math.min(100, Math.max(0, ((value - min) / span) * 100))
  }
  const bandLeft = clamp(metric.band_low)
  const bandRight = clamp(metric.band_high)
  return {
    bandLeft,
    bandWidth: Math.max(0, bandRight - bandLeft),
    mark: clamp(metric.value),
  }
}
