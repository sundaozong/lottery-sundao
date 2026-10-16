<template>
  <div>
    <div class="page-header">
      <div>
        <h1>购买记录</h1>
        <p>流水 · 盈亏汇总 · CRUD</p>
      </div>
      <button class="btn btn-primary btn-sm" type="button" @click="showForm = !showForm">
        {{ showForm ? '收起' : '+ 记一笔' }}
      </button>
    </div>

    <div class="grid grid-3 mb-4">
      <div class="card stat">
        <div class="stat-label">投入</div>
        <div class="stat-value">¥ {{ summary.total_cost ?? 0 }}</div>
      </div>
      <div class="card stat">
        <div class="stat-label">奖金</div>
        <div class="stat-value ok">¥ {{ summary.total_prize ?? 0 }}</div>
      </div>
      <div class="card stat">
        <div class="stat-label">净盈亏</div>
        <div class="stat-value" :class="(summary.net || 0) >= 0 ? 'ok' : 'danger'">
          ¥ {{ summary.net ?? 0 }}
        </div>
      </div>
    </div>

    <div v-if="showForm" class="card mb-4">
      <div class="card-title">{{ editingId ? '编辑记录' : '新增记录' }}</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">彩种</label>
          <select v-model="form.lottery_type" class="form-select">
            <option v-for="(name, key) in TYPE_NAMES" :key="key" :value="key">{{ name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">期号</label>
          <input v-model="form.issue" class="form-input" placeholder="如 2026101" />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">号码（主号空格分隔，蓝/后区用 | 分隔）</label>
        <input v-model="form.numbersText" class="form-input" placeholder="03 12 18 22 27 31 | 09" />
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">投入(元)</label>
          <input v-model.number="form.cost" type="number" step="0.01" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">奖金(元)</label>
          <input v-model.number="form.prize" type="number" step="0.01" class="form-input" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">购买日期</label>
          <input v-model="form.purchased_at" class="form-input" placeholder="2026-10-15" />
        </div>
        <div class="form-group">
          <label class="form-label">备注</label>
          <input v-model="form.note" class="form-input" />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="button" @click="save">保存</button>
        <button class="btn btn-ghost" type="button" @click="resetForm">取消</button>
      </div>
    </div>

    <div class="card">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>彩种</th><th>期号</th><th>号码</th><th>投入</th><th>奖金</th><th>盈亏</th><th>日期</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in items" :key="r.id">
              <td>{{ r.name }}</td>
              <td class="mono">{{ r.issue }}</td>
              <td><NumberBalls :numbers="r.numbers" :type="r.lottery_type" size="sm" /></td>
              <td class="mono">{{ r.cost }}</td>
              <td class="mono">{{ r.prize }}</td>
              <td class="mono" :class="r.profit >= 0 ? 'profit-pos' : 'profit-neg'">{{ r.profit }}</td>
              <td class="text-xs">{{ r.purchased_at }}</td>
              <td>
                <button class="btn btn-ghost btn-sm" type="button" @click="edit(r)">改</button>
                <button class="btn btn-danger btn-sm" type="button" @click="remove(r.id)">删</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!items.length" class="empty"><div class="icon">☰</div>暂无记录</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api, TYPE_NAMES } from '../api'
import NumberBalls from '../components/NumberBalls.vue'

const items = ref([])
const summary = ref({})
const showForm = ref(false)
const editingId = ref(null)
const form = ref(blank())

function blank() {
  return {
    lottery_type: 'ssq',
    issue: '',
    numbersText: '',
    cost: 2,
    prize: 0,
    note: '',
    purchased_at: new Date().toISOString().slice(0, 10),
  }
}

function parseNumbersText(text) {
  const parts = text.split('|')
  const main = (parts[0] || '').trim().split(/[\s,]+/).filter(Boolean)
  const special = (parts[1] || '').trim().split(/[\s,]+/).filter(Boolean)
  return { main, special }
}

async function load() {
  const res = await api.records()
  items.value = res.items || []
  summary.value = res.summary || {}
}

function resetForm() {
  form.value = blank()
  editingId.value = null
  showForm.value = false
}

function edit(r) {
  editingId.value = r.id
  showForm.value = true
  const m = (r.numbers.main || []).join(' ')
  const s = (r.numbers.special || []).join(' ')
  form.value = {
    lottery_type: r.lottery_type,
    issue: r.issue,
    numbersText: s ? `${m} | ${s}` : m,
    cost: r.cost,
    prize: r.prize,
    note: r.note,
    purchased_at: r.purchased_at,
  }
}

async function save() {
  const body = {
    lottery_type: form.value.lottery_type,
    issue: form.value.issue,
    numbers: parseNumbersText(form.value.numbersText),
    cost: form.value.cost,
    prize: form.value.prize,
    note: form.value.note,
    purchased_at: form.value.purchased_at,
  }
  try {
    if (editingId.value) await api.updateRecord(editingId.value, body)
    else await api.createRecord(body)
    resetForm()
    await load()
  } catch (e) {
    alert(e.message)
  }
}

async function remove(id) {
  if (!confirm('确认删除？')) return
  await api.deleteRecord(id)
  await load()
}

onMounted(load)
</script>
