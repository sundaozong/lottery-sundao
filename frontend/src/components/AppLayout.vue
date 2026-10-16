<template>
  <div class="app">
    <header class="topbar">
      <div class="flex gap-3" style="align-items:center">
        <button class="menu-toggle" type="button" aria-label="菜单" @click="sidebarOpen = !sidebarOpen">☰</button>
        <router-link class="brand" to="/">
          <div class="brand-mark">孙</div>
          <div>孙导带你夜夜笙歌 <span class="tag">{{ dataTag }}</span></div>
        </router-link>
      </div>
      <div class="topbar-actions">
        <button class="btn btn-ghost btn-sm" type="button" :disabled="syncing" @click="onSync">
          {{ syncing ? '同步中…' : '↻ 同步' }}
        </button>
        <router-link class="btn btn-ghost btn-sm" to="/settings">设置</router-link>
      </div>
    </header>

    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="nav-label">总览</div>
      <router-link class="nav-item" to="/" @click="sidebarOpen = false"><span class="icon">◈</span> 首页</router-link>
      <div class="nav-label">观测</div>
      <router-link class="nav-item" to="/analysis" @click="sidebarOpen = false"><span class="icon">▣</span> 分析中心</router-link>
      <router-link class="nav-item" to="/predict" @click="sidebarOpen = false"><span class="icon">✦</span> 预测 / 推荐</router-link>
      <div class="nav-label">账本</div>
      <router-link class="nav-item" to="/records" @click="sidebarOpen = false"><span class="icon">☰</span> 购买记录</router-link>
      <router-link class="nav-item" to="/prize" @click="sidebarOpen = false"><span class="icon">¥</span> 奖金计算</router-link>
      <div class="nav-label">系统</div>
      <router-link class="nav-item" to="/settings" @click="sidebarOpen = false"><span class="icon">⚙</span> 邮件 / 爬取</router-link>
    </aside>

    <main class="main">
      <router-view />
      <div class="page-foot">孙导带你夜夜笙歌 · 个人观测 · 预测仅供娱乐 · 请理性购彩</div>
    </main>

    <nav class="mobile-tabs">
      <router-link class="mobile-tab" to="/"><span class="mi">◈</span>首页</router-link>
      <router-link class="mobile-tab" to="/analysis"><span class="mi">▣</span>分析</router-link>
      <router-link class="mobile-tab" to="/predict"><span class="mi">✦</span>预测</router-link>
      <router-link class="mobile-tab" to="/records"><span class="mi">☰</span>记录</router-link>
      <router-link class="mobile-tab" to="/settings"><span class="mi">⚙</span>更多</router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const sidebarOpen = ref(false)
const syncing = ref(false)
const dataTag = ref('本地')

async function onSync() {
  syncing.value = true
  try {
    const res = await api.crawl()
    dataTag.value = res.errors?.length ? '混合' : '已同步'
    alert(res.message + (res.errors?.length ? '\n' + res.errors.slice(0, 3).join('\n') : ''))
  } catch (e) {
    alert('同步失败: ' + e.message)
  } finally {
    syncing.value = false
  }
}

onMounted(async () => {
  try {
    const latest = await api.latest()
    const sources = (latest.items || []).map((i) => i.source)
    if (sources.some((s) => s === 'crawl') && sources.some((s) => s === 'seed')) dataTag.value = '混合'
    else if (sources.every((s) => s === 'crawl')) dataTag.value = '爬取'
    else dataTag.value = '示例'
  } catch {
    dataTag.value = '离线'
  }
})
</script>
