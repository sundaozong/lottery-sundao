<template>
  <div>
    <div class="page-header">
      <div>
        <h1>邮件 / 爬取</h1>
        <p>订阅彩种 · 爬取间隔 · SMTP 推送</p>
      </div>
    </div>

    <div class="alert" :class="settings.smtp_configured ? 'alert-ok' : 'alert-warn'">
      <AppIcon
        :name="settings.smtp_configured ? 'checkCircle' : 'alert'"
        :size="14"
        style="margin-top:2px;flex:none"
      />
      <div>
        SMTP
        <strong>{{ settings.smtp_configured ? '已配置（环境变量）' : '未配置' }}</strong>
        — 未配置时测试邮件会返回友好提示。请在项目根目录 `.env` 填写 SMTP_* 。
      </div>
    </div>

    <div class="grid grid-2 mb-4">
      <div class="card">
        <div class="card-title">爬取设置</div>
        <div class="form-group">
          <label class="form-label">间隔（分钟）</label>
          <input v-model.number="settings.crawl_interval_minutes" type="number" min="5" class="form-input" />
          <p class="form-hint">定时任务在后端启动时读取；改后建议重启 uvicorn 生效。</p>
        </div>
        <div class="form-group">
          <label class="form-label">订阅彩种</label>
          <div class="chip-row">
            <button
              v-for="(name, key) in TYPE_NAMES"
              :key="key"
              type="button"
              class="chip"
              :class="{ active: settings.subscribed_types.includes(key) }"
              @click="toggleType(key)"
            >{{ name }}</button>
          </div>
        </div>
        <button class="btn btn-ghost" type="button" :disabled="crawling" @click="doCrawl">
          <AppIcon v-if="crawling" name="sync" :size="14" class="spin" />
          {{ crawling ? '爬取中…' : '立即爬取' }}
        </button>
        <p v-if="crawlMsg" class="form-hint mt-2">{{ crawlMsg }}</p>
      </div>

      <div class="card">
        <div class="card-title">邮件推送</div>
        <div class="toggle">
          <div>
            <div class="text-sm">启用推送开关</div>
            <div class="text-xs text-muted">本地标记；实际发送仍需 SMTP</div>
          </div>
          <div
            class="switch"
            :class="{ on: settings.mail_enabled }"
            role="switch"
            tabindex="0"
            :aria-checked="settings.mail_enabled"
            aria-label="启用邮件推送"
            @click="settings.mail_enabled = !settings.mail_enabled"
            @keydown.enter.prevent="settings.mail_enabled = !settings.mail_enabled"
            @keydown.space.prevent="settings.mail_enabled = !settings.mail_enabled"
          ></div>
        </div>
        <div class="form-group mt-3">
          <label class="form-label">收件邮箱</label>
          <input v-model="settings.mail_to" class="form-input" placeholder="you@example.com" />
        </div>
        <div class="form-actions">
          <button class="btn btn-ghost" type="button" @click="testMail"><AppIcon name="mail" :size="14" />发送测试邮件</button>
          <button class="btn btn-ghost" type="button" @click="digestMail"><AppIcon name="mail" :size="14" />推送开奖摘要</button>
        </div>
        <p v-if="mailMsg" class="form-hint mt-2">{{ mailMsg }}</p>
      </div>
    </div>

    <button class="btn btn-primary" type="button" @click="save"><AppIcon name="check" :size="14" />保存设置</button>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api, TYPE_NAMES } from '../api'
import AppIcon from '../components/AppIcon.vue'
import { toast } from '../composables/feedback'

const settings = ref({
  crawl_interval_minutes: 60,
  subscribed_types: [],
  mail_enabled: false,
  mail_to: '',
  smtp_configured: false,
})
const crawling = ref(false)
const crawlMsg = ref('')
const mailMsg = ref('')

function toggleType(key) {
  const arr = settings.value.subscribed_types
  const i = arr.indexOf(key)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(key)
}

async function save() {
  try {
    settings.value = await api.saveSettings({
      crawl_interval_minutes: settings.value.crawl_interval_minutes,
      subscribed_types: settings.value.subscribed_types,
      mail_enabled: settings.value.mail_enabled,
      mail_to: settings.value.mail_to,
    })
    toast('设置已保存', 'ok')
  } catch (e) {
    toast(e.message, 'error', 4000)
  }
}

async function doCrawl() {
  crawling.value = true
  crawlMsg.value = ''
  try {
    const res = await api.crawl()
    crawlMsg.value = res.message + (res.errors?.length ? ' | ' + res.errors[0] : '')
  } catch (e) {
    crawlMsg.value = e.message
  } finally {
    crawling.value = false
  }
}

async function testMail() {
  mailMsg.value = ''
  const res = await api.mailTest(settings.value.mail_to)
  mailMsg.value = res.ok ? res.message : res.error
}

async function digestMail() {
  mailMsg.value = ''
  const res = await api.mailDigest()
  mailMsg.value = res.ok ? res.message : res.error
}

onMounted(async () => {
  settings.value = await api.settings()
})
</script>
