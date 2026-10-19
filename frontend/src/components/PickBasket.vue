<template>
  <div v-if="isOpen" class="basket-mask" @click.self="hide">
    <aside class="basket-drawer" role="dialog" aria-modal="true" aria-label="选号篮">
      <header class="basket-head">
        <div>
          <div class="basket-title">选号篮</div>
          <p class="form-hint">{{ typeName }} {{ count }} 注 · 全部 {{ total }} 注 · 只存在这台浏览器</p>
        </div>
        <button class="icon-btn" type="button" aria-label="关闭选号篮" @click="hide">
          <AppIcon name="x" />
        </button>
      </header>

      <div class="basket-scroll">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:2px;flex:none" />
          <div>选号篮只是暂存号码。<strong>不构成投注建议</strong>，也不代表会中奖。</div>
        </div>

        <div class="chip-row">
          <button
            v-for="(name, key) in TYPE_NAMES"
            :key="key"
            type="button"
            class="chip"
            :class="{ active: viewType === key }"
            @click="setViewType(key)"
          >{{ name }}<template v-if="counts[key]"> {{ counts[key] }}</template></button>
        </div>

        <div class="basket-collision">
          <div class="card-title">撞号提示 <span class="sub">只看当前彩种</span></div>
          <p class="basket-summary">{{ collision.summary }}</p>
          <div v-if="collision.repeatedMain.length" class="basket-hit-row">
            <span
              v-for="hit in collision.repeatedMain"
              :key="(hit.positionLabel || '') + hit.n"
              class="basket-hit"
            >
              <span v-if="hit.positionLabel" class="pos-label">{{ hit.positionLabel }}</span>
              <span class="ball sm" :class="mainColor">{{ hit.n }}</span>
              <span class="basket-hit-count">×{{ hit.count }}</span>
            </span>
          </div>
          <div v-if="collision.repeatedSpecial.length" class="basket-hit-row">
            <span v-for="hit in collision.repeatedSpecial" :key="'s' + hit.n" class="basket-hit">
              <span class="pos-label">{{ profile?.specialLabel || '特别' }}</span>
              <span class="ball sm" :class="profile?.specialColor || 'blue'">{{ hit.n }}</span>
              <span class="basket-hit-count">×{{ hit.count }}</span>
            </span>
          </div>
          <p v-for="pair in collision.pairs.slice(0, 6)" :key="pair.left + '-' + pair.right" class="form-hint">
            第 {{ pair.left }} 注和第 {{ pair.right }} 注：{{ pair.waste }}
          </p>
          <div v-if="collision.holes.length" class="mt-2">
            <div class="form-hint">没覆盖到的主号</div>
            <div class="basket-holes">
              <span v-for="n in collision.holes" :key="n" class="ball ghost sm">{{ n }}</span>
            </div>
          </div>
          <p class="form-hint">{{ collision.disclaimer }}</p>
        </div>

        <div v-if="!visible.length" class="empty">
          <div class="icon"><AppIcon name="inbox" :size="22" /></div>
          <div class="empty-title">这彩种还是空的</div>
          <div class="empty-desc">从预测页加入，或在下面粘贴、手工点一注</div>
        </div>

        <div v-else class="basket-list">
          <div v-for="(item, index) in visible" :key="item.id" class="basket-item">
            <div class="basket-item-top">
              <span class="predict-row-label">第 {{ index + 1 }} 注</span>
              <span class="text-xs text-muted">{{ sourceText(item) }} · {{ timeLabel(item.added_at) }}</span>
              <button class="btn btn-ghost btn-sm" type="button" @click="checkItem(item)">体检</button>
              <button class="btn btn-ghost btn-sm" type="button" @click="replayItem(item)">回放</button>
              <button class="icon-btn danger" type="button" title="移出" aria-label="移出这注" @click="remove(item.id)">
                <AppIcon name="trash" />
              </button>
            </div>
            <NumberBalls :numbers="item.numbers" :type="item.lottery_type" size="sm" />
            <p v-if="item.note" class="form-hint">{{ item.note }}</p>
            <p v-if="betsOf(item) > 1" class="form-hint">按复式计 {{ betsOf(item) }} 注 · ¥ {{ costOf(item) }}</p>
          </div>
        </div>

        <div class="basket-paste">
          <button class="btn btn-ghost btn-sm" type="button" @click="showPaste = !showPaste">
            {{ showPaste ? '收起粘贴导入' : '粘贴导入' }}
          </button>
          <template v-if="showPaste">
            <label class="form-label" for="basket-paste-input">一行一注</label>
            <p class="form-hint">号码之间用空格或逗号，特别号前加 + 或 |。空行、彩种名和免责声明会跳过。</p>
            <textarea
              id="basket-paste-input"
              v-model="pasteText"
              class="form-textarea basket-paste-input"
              rows="5"
              :placeholder="pastePlaceholder"
              spellcheck="false"
            />
            <p v-if="pasteActive" class="basket-paste-summary">
              将加入 {{ pastePreview.added }} · 重复 {{ pastePreview.duplicates }} · 无效 {{ pastePreview.invalidCount }}
            </p>
            <ul v-if="pastePreview.errors.length" class="basket-paste-errors">
              <li v-for="err in pastePreview.errors" :key="err.line">第 {{ err.line }} 行：{{ err.message }}</li>
            </ul>
            <p v-if="pastePreview.invalidCount > pastePreview.errors.length" class="form-hint">其余无效行已省略</p>
            <button class="btn btn-primary btn-sm" type="button" @click="confirmPaste">解析并放入</button>
          </template>
        </div>

        <div class="basket-manual">
          <button class="btn btn-ghost btn-sm" type="button" @click="showManual = !showManual">
            {{ showManual ? '收起手工加号' : '手工加一注' }}
          </button>
          <template v-if="showManual && profile">
            <p class="form-hint">{{ manualHint }}</p>
            <template v-if="profile.mode === 'digit'">
              <div v-for="(label, index) in profile.positions" :key="label" class="form-group">
                <label class="form-label">{{ label }}</label>
                <NumberPad
                  :from="profile.mainLo"
                  :to="profile.mainHi"
                  :pad="profile.width"
                  :color="profile.mainColor"
                  :max="1"
                  :selected="manualPositions[index] || []"
                  @update:selected="setPosition(index, $event)"
                />
              </div>
              <div v-if="profile.specCount" class="form-group">
                <label class="form-label">{{ profile.specialLabel }}</label>
                <NumberPad
                  :from="profile.specLo"
                  :to="profile.specHi"
                  :pad="1"
                  :color="profile.specialColor"
                  :max="1"
                  :selected="manualPositions[profile.positions.length] || []"
                  @update:selected="setPosition(profile.positions.length, $event)"
                />
              </div>
            </template>
            <template v-else>
              <div class="form-group">
                <label class="form-label">主号</label>
                <NumberPad
                  :from="profile.mainLo"
                  :to="profile.mainHi"
                  :pad="profile.width"
                  :color="profile.mainColor"
                  :max="profile.manualMax || profile.mainCount || profile.mainMax"
                  :min="profile.manualMin || profile.mainCount || profile.mainMin || 0"
                  :selected="manualMain"
                  @update:selected="manualMain = $event"
                />
              </div>
              <div v-if="profile.specCount" class="form-group">
                <label class="form-label">{{ profile.specialLabel }}</label>
                <NumberPad
                  :from="profile.specLo"
                  :to="profile.specHi"
                  :pad="profile.width"
                  :color="profile.specialColor"
                  :max="profile.specCount"
                  :min="profile.specCount"
                  :selected="manualSpecial"
                  @update:selected="manualSpecial = $event"
                />
              </div>
            </template>
            <button class="btn btn-primary btn-sm" type="button" @click="addManual">放入选号篮</button>
          </template>
        </div>
      </div>

      <footer class="basket-foot">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">期号</label>
            <input v-model="issue" class="form-input" placeholder="可留空，或填待定 / 本期期号" />
          </div>
          <div class="form-group">
            <label class="form-label">倍数</label>
            <input v-model.number="multiple" class="form-input" type="number" min="1" />
          </div>
        </div>
        <p class="form-hint">写入当前彩种 {{ count }} 注 · 估算 ¥ {{ previewCost }} · 单注 2 元 × 倍数</p>
        <label class="basket-check">
          <input v-model="removeAfter" type="checkbox" />
          写入后从篮中移除
        </label>
        <div class="basket-actions">
          <button class="btn btn-ghost btn-sm" type="button" :disabled="!count" @click="copyAll">复制全部号码</button>
          <button class="btn btn-ghost btn-sm" type="button" :disabled="!count" @click="onClearType">清空本彩种</button>
          <button class="btn btn-ghost btn-sm" type="button" :disabled="!total" @click="onClearAll">清空全部</button>
          <button class="btn btn-primary btn-sm" type="button" :disabled="!count || saving" @click="commit">
            {{ saving ? '写入中…' : '写入购彩记录' }}
          </button>
        </div>
      </footer>
    </aside>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, TYPE_NAMES, ballClass } from '../api'
import { basketProfile, betCount, formatBasketText, lineCost, sourceLabel, writeBasketRecords } from '../lib/basket'
import { previewBasketPaste } from '../lib/basketPaste'
import { useBasket } from '../composables/useBasket'
import { useReplay } from '../composables/useReplay'
import { confirmDialog, toast } from '../composables/feedback'
import NumberBalls from './NumberBalls.vue'
import NumberPad from './NumberPad.vue'
import AppIcon from './AppIcon.vue'

const {
  visible,
  viewType,
  isOpen,
  count,
  total,
  counts,
  collision,
  setViewType,
  hide,
  add,
  addMany,
  remove,
  clearCurrent,
  clearAll,
  dropIds,
} = useBasket()
const replay = useReplay()

const router = useRouter()

const issue = ref('')
const multiple = ref(1)
const removeAfter = ref(true)
const saving = ref(false)
const showManual = ref(false)
const showPaste = ref(false)
const pasteText = ref('')
const manualMain = ref([])
const manualSpecial = ref([])
const manualPositions = ref([])

const profile = computed(() => basketProfile(viewType.value))
const typeName = computed(() => TYPE_NAMES[viewType.value] || viewType.value)
const mainColor = computed(() => ballClass(viewType.value, 'main'))
const previewCost = computed(() => visible.value.reduce(
  (sum, item) => sum + lineCost(item.lottery_type, item.numbers, multiple.value),
  0,
))
const pastePreview = computed(() => previewBasketPaste(visible.value, viewType.value, pasteText.value))
const pasteActive = computed(() => pastePreview.value.drafts.length > 0 || pastePreview.value.invalidCount > 0)
const pastePlaceholder = computed(() => {
  const spec = profile.value
  if (!spec) return ''
  if (viewType.value === 'kl8') return '01 02 03 04 05'
  if (spec.mode === 'digit') {
    const main = Array.from({ length: spec.mainCount }, (_, index) => String((index + 1) % 10)).join(' ')
    return spec.specCount ? `${main} + 7` : main
  }
  const main = Array.from({ length: spec.mainCount }, (_, index) => String(index + 1).padStart(spec.width, '0')).join(' ')
  if (!spec.specCount) return main
  const special = Array.from({ length: spec.specCount }, (_, index) => String(index + 1).padStart(spec.width, '0')).join(' ')
  return `${main} + ${special}`
})
const manualHint = computed(() => {
  if (viewType.value === 'kl8') return '点 1–10 个，按选一到选十记一注。预测生成的 20 个号会按选十复式计费。'
  if (profile.value?.mode === 'digit') return '每个位置点一个数字。顺序就是号码。'
  return '点满一注再放入。和篮里已有的号码相同会被拦住。'
})

function resetManual() {
  const spec = profile.value
  manualMain.value = []
  manualSpecial.value = []
  const slots = (spec?.positions?.length || 0) + (spec?.specCount ? 1 : 0)
  manualPositions.value = Array.from({ length: slots }, () => [])
}

function setPosition(index, value) {
  const next = manualPositions.value.slice()
  next[index] = value
  manualPositions.value = next
}

function sourceText(item) {
  return sourceLabel(item)
}

function timeLabel(iso) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function betsOf(item) {
  return betCount(item.lottery_type, item.numbers)
}

function costOf(item) {
  return lineCost(item.lottery_type, item.numbers, multiple.value)
}

function replayItem(item) {
  replay.openTicket({
    lotteryType: item.lottery_type,
    numbers: item.numbers,
  })
}

function checkItem(item) {
  hide()
  router.push({
    path: '/predict',
    query: {
      check: item.lottery_type,
      main: (item.numbers?.main || []).join(','),
      special: (item.numbers?.special || []).join(','),
    },
  })
}

function confirmPaste() {
  const summary = pastePreview.value
  if (!summary.drafts.length && !summary.invalidCount) {
    toast('没有可解析的号码', 'info')
    return
  }
  if (!summary.added) {
    const head = []
    if (summary.duplicates) head.push(`重复 ${summary.duplicates} 注`)
    if (summary.invalidCount) head.push(`无效 ${summary.invalidCount} 行`)
    const reason = summary.errors[0] ? `第 ${summary.errors[0].line} 行：${summary.errors[0].message}` : ''
    toast([...head, reason].filter(Boolean).join('，') || '没有新号码', summary.invalidCount ? 'error' : 'info')
    return
  }
  const result = addMany(summary.drafts)
  const parts = [`已加入 ${result.added} 注`]
  if (result.duplicates) parts.push(`重复 ${result.duplicates} 注`)
  if (summary.invalidCount) parts.push(`无效 ${summary.invalidCount} 行`)
  toast(parts.join('，'), summary.invalidCount ? 'info' : 'ok')
  if (!summary.invalidCount) pasteText.value = ''
}

function addManual() {
  const spec = profile.value
  if (!spec) return
  let numbers
  if (spec.mode === 'digit') {
    const main = (spec.positions || []).map((_, index) => (manualPositions.value[index] || [])[0]).filter(Boolean)
    const special = spec.specCount ? (manualPositions.value[spec.positions.length] || []) : []
    numbers = { main, special }
  } else {
    numbers = { main: manualMain.value, special: manualSpecial.value }
  }
  const result = add({
    lottery_type: viewType.value,
    numbers,
    source: 'manual',
  })
  toast(result.message, result.status === 'added' ? 'ok' : result.status === 'duplicate' ? 'info' : 'error')
  if (result.status === 'added') resetManual()
}

async function copyAll() {
  const text = formatBasketText(visible.value, viewType.value)
  if (!text) {
    toast('当前彩种篮是空的', 'info')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    toast('已复制号码', 'ok')
    return
  } catch {
    /* 浏览器拦住剪贴板时，退回选中文本复制 */
  }
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.left = '-9999px'
    document.body.appendChild(area)
    area.select()
    const copied = document.execCommand('copy')
    area.remove()
    toast(copied ? '已复制号码' : '复制失败，请检查浏览器权限', copied ? 'ok' : 'error')
  } catch {
    toast('复制失败，请检查浏览器权限', 'error')
  }
}

async function onClearType() {
  const ok = await confirmDialog({
    title: '清空本彩种',
    message: `从选号篮拿掉全部${typeName.value}？其他彩种还留着。`,
    confirmText: '清空',
  })
  if (!ok) return
  clearCurrent()
  toast(`已清空${typeName.value}`, 'ok')
}

async function onClearAll() {
  const ok = await confirmDialog({
    title: '清空全部',
    message: '选号篮里的所有彩种都会拿掉。已经写入购彩记录的不受影响。',
    confirmText: '全部清空',
  })
  if (!ok) return
  clearAll()
  toast('选号篮已清空', 'ok')
}

async function commit() {
  if (!visible.value.length || saving.value) return
  const rows = visible.value.slice()
  saving.value = true
  try {
    const outcome = await writeBasketRecords(rows, (body) => api.createRecord(body), {
      issue: issue.value,
      multiple: Math.max(1, Number(multiple.value) || 1),
    })
    if (removeAfter.value && outcome.createdIds.length) dropIds(outcome.createdIds)
    if (!outcome.errors.length) {
      toast(`已写入 ${outcome.createdIds.length} 条购彩记录`, 'ok')
      return
    }
    const reason = outcome.errors[0]?.message || '写入失败'
    if (outcome.createdIds.length) {
      toast(`写入 ${outcome.createdIds.length} 条，失败 ${outcome.errors.length} 条：${reason}`, 'info', 4200)
      return
    }
    toast(reason, 'error', 4200)
  } finally {
    saving.value = false
  }
}

function onKey(event) {
  if (event.key === 'Escape' && isOpen.value) hide()
}

watch(viewType, () => {
  resetManual()
})

watch(isOpen, (open) => {
  if (open) resetManual()
})

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>
