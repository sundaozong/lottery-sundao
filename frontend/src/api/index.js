async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = data.detail || data.error || res.statusText
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

export const api = {
  health: () => request('/api/health'),
  meta: () => request('/api/draws/meta'),
  latest: () => request('/api/draws/latest'),
  draws: (type, limit = 30) =>
    request(`/api/draws?${new URLSearchParams({ ...(type ? { lottery_type: type } : {}), limit })}`),
  crawl: (type) =>
    request(`/api/draws/crawl${type ? `?lottery_type=${type}` : ''}`, { method: 'POST' }),
  analysis: (type, limit = 50) => request(`/api/analysis/${type}?limit=${limit}`),
  shape: (type, limit = 50) => request(`/api/analysis/${type}/shape?limit=${limit}`),
  affinity: (type, { limit = 50, seed } = {}) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (seed) params.set('seed', seed)
    return request(`/api/analysis/${type}/affinity?${params}`)
  },
  echo: (type, body) => request(`/api/analysis/${type}/echo`, { method: 'POST', body: JSON.stringify(body) }),
  collision: (type, body) => request(`/api/analysis/${type}/collision`, { method: 'POST', body: JSON.stringify(body) }),
  repeat: (type, limit = 80) => request(`/api/analysis/${type}/repeat?limit=${limit}`),
  repeatScore: (type, body) => request(`/api/analysis/${type}/repeat`, { method: 'POST', body: JSON.stringify(body) }),
  momentum: (type, { limit = 80, short = 10, long = 50 } = {}) => {
    const params = new URLSearchParams({
      limit: String(limit),
      short: String(short),
      long: String(long),
    })
    return request(`/api/analysis/${type}/momentum?${params}`)
  },
  momentumScore: (type, body) => request(`/api/analysis/${type}/momentum`, { method: 'POST', body: JSON.stringify(body) }),
  neighbor: (type, { limit = 80, horizon = 3 } = {}) => {
    const params = new URLSearchParams({
      limit: String(limit),
      horizon: String(horizon),
    })
    return request(`/api/analysis/${type}/neighbor?${params}`)
  },
  neighborScore: (type, body) => request(`/api/analysis/${type}/neighbor`, { method: 'POST', body: JSON.stringify(body) }),
  predict: (body) => request('/api/predict', { method: 'POST', body: JSON.stringify(body) }),
  records: () => request('/api/records'),
  recordMonths: () => request('/api/records/monthly'),
  rhythm: () => request('/api/records/rhythm'),
  createRecord: (body) => request('/api/records', { method: 'POST', body: JSON.stringify(body) }),
  updateRecord: (id, body) => request(`/api/records/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteRecord: (id) => request(`/api/records/${id}`, { method: 'DELETE' }),
  prizeRules: () => request('/api/prize/rules'),
  prizeCalc: (body) => request('/api/prize/calc', { method: 'POST', body: JSON.stringify(body) }),
  backtest: (body) => request('/api/prize/backtest', { method: 'POST', body: JSON.stringify(body) }),
  settings: () => request('/api/settings'),
  saveSettings: (body) => request('/api/settings', { method: 'PUT', body: JSON.stringify(body) }),
  mailTest: (to) => request('/api/mail/test', { method: 'POST', body: JSON.stringify({ to }) }),
  mailDigest: () => request('/api/mail/digest', { method: 'POST' }),
  mailPredict: (body) => request('/api/mail/predict', { method: 'POST', body: JSON.stringify(body) }),
}

export function getMomentum(type, params) {
  return api.momentum(type, params)
}

export function postMomentum(type, body) {
  return api.momentumScore(type, body)
}

export function getNeighbor(type, params) {
  return api.neighbor(type, params)
}

export function postNeighbor(type, body) {
  return api.neighborScore(type, body)
}

export async function downloadRecords() {
  const res = await fetch('/api/records/export')
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const msg = data.detail || data.error || res.statusText
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return res.blob()
}

export const TYPE_NAMES = {
  ssq: '双色球',
  dlt: '大乐透',
  fc3d: '福彩3D',
  pl3: '排列三',
  pl5: '排列五',
  qxc: '七星彩',
  qlc: '七乐彩',
  kl8: '快乐八',
}

/** 开奖星期，JS Date.getDay()：0 周日 … 6 周六。null 表示每天。 */
export const DRAW_WEEKDAYS = {
  ssq: [0, 2, 4],
  dlt: [1, 3, 6],
  fc3d: null,
  pl3: null,
  pl5: null,
  qxc: [0, 2, 5],
  qlc: [1, 3, 5],
  kl8: null,
}

const WEEKDAY_LABELS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

export function lotteriesOn(date = new Date()) {
  const day = date.getDay()
  const today = []
  const off = []
  for (const [type, name] of Object.entries(TYPE_NAMES)) {
    const days = DRAW_WEEKDAYS[type]
    const item = { type, name }
    if (days == null || days.includes(day)) today.push(item)
    else off.push(item)
  }
  return {
    today,
    off,
    label: `${WEEKDAY_LABELS[day]} · ${date.getMonth() + 1}月${date.getDate()}日`,
  }
}

export function ballClass(type, kind = 'main') {
  if (type === 'ssq' || type === 'dlt' || type === 'qlc') return kind === 'special' ? 'blue' : 'red'
  if (type === 'qxc') return kind === 'special' ? 'orange' : 'purple'
  if (type === 'kl8') return 'orange'
  return 'green'
}
