import { computed, reactive } from 'vue'
import {
  addManyToBasket,
  addToBasket,
  basketCollision,
  clearBasket,
  clearLottery,
  itemsForLottery,
  loadBasket,
  removeFromBasket,
  saveBasket,
} from '../lib/basket'
import { applySnapshot } from '../lib/basketSnapshots'

const VIEW_KEY = 'yysg.pick.basket.view'

function readViewType() {
  try {
    return localStorage.getItem(VIEW_KEY) || 'ssq'
  } catch {
    return 'ssq'
  }
}

const state = reactive({
  items: loadBasket(localStorage),
  viewType: readViewType(),
  open: false,
})

function persist() {
  saveBasket(localStorage, state.items)
}

export function useBasket() {
  function setViewType(type) {
    if (!type || type === state.viewType) return
    state.viewType = type
    try {
      localStorage.setItem(VIEW_KEY, type)
    } catch {
      /* 隐私模式写不进时，当前页仍用内存里的彩种 */
    }
  }

  function add(draft) {
    const result = addToBasket(state.items, draft)
    if (result.status === 'added') {
      state.items = result.items
      persist()
    }
    if (draft?.lottery_type) setViewType(draft.lottery_type)
    return result
  }

  function addMany(drafts) {
    const result = addManyToBasket(state.items, drafts)
    if (result.added) {
      state.items = result.items
      persist()
    }
    if (drafts?.[0]?.lottery_type) setViewType(drafts[0].lottery_type)
    return result
  }

  function remove(id) {
    state.items = removeFromBasket(state.items, id)
    persist()
  }

  function clearCurrent() {
    state.items = clearLottery(state.items, state.viewType)
    persist()
  }

  function clearAll() {
    state.items = clearBasket()
    persist()
  }

  function dropIds(ids) {
    const gone = new Set(ids || [])
    state.items = state.items.filter((item) => !gone.has(item.id))
    persist()
  }

  function installSnapshot(snapshot) {
    const result = applySnapshot(state.items, snapshot)
    if (result.ok) {
      state.items = result.items
      persist()
    }
    return result
  }

  return {
    visible: computed(() => itemsForLottery(state.items, state.viewType)),
    viewType: computed(() => state.viewType),
    isOpen: computed(() => state.open),
    count: computed(() => itemsForLottery(state.items, state.viewType).length),
    total: computed(() => state.items.length),
    counts: computed(() => {
      const map = {}
      for (const item of state.items) map[item.lottery_type] = (map[item.lottery_type] || 0) + 1
      return map
    }),
    collision: computed(() => basketCollision(state.viewType, state.items)),
    setViewType,
    show() {
      state.open = true
    },
    hide() {
      state.open = false
    },
    add,
    addMany,
    remove,
    clearCurrent,
    clearAll,
    dropIds,
    installSnapshot,
  }
}
