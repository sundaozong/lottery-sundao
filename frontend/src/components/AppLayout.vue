<template>
  <div class="app">
    <header class="topbar">
      <div class="flex gap-3" style="align-items:center">
        <button class="menu-toggle" type="button" aria-label="打开菜单" @click="sidebarOpen = true">
          <AppIcon name="menu" />
        </button>
        <router-link class="brand" to="/">
          <div class="brand-mark">孙</div>
          <div>孙导带你夜夜笙歌 <span class="tag">{{ dataTag }}</span></div>
        </router-link>
      </div>
      <div class="topbar-actions">
        <button class="btn btn-ghost btn-sm" type="button" @click="openBasket">
          <AppIcon name="basket" />
          <span class="basket-label">选号篮</span>
          <span v-if="basketCount" class="basket-badge">{{ basketCount }}</span>
        </button>
        <button class="btn btn-ghost btn-sm" type="button" :disabled="syncing" @click="onSync">
          <AppIcon name="sync" :class="{ spin: syncing }" />
          {{ syncing ? '同步中…' : '同步' }}
        </button>
        <router-link class="btn btn-ghost btn-sm" to="/settings">
          <AppIcon name="settings" />设置
        </router-link>
      </div>
    </header>

    <div
      class="sidebar-backdrop"
      :class="{ show: sidebarOpen }"
      @click="sidebarOpen = false"
    ></div>

    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="nav-label">总览</div>
      <router-link class="nav-item" to="/" @click="sidebarOpen = false"><AppIcon name="home" /> 首页</router-link>
      <div class="nav-label">观测</div>
      <router-link class="nav-item" to="/analysis" @click="sidebarOpen = false"><AppIcon name="chart" /> 分析中心</router-link>
      <router-link class="nav-item" to="/predict" @click="sidebarOpen = false"><AppIcon name="sparkle" /> 预测 / 推荐</router-link>
      <div class="nav-label">账本</div>
      <button class="nav-item basket-nav" type="button" @click="openBasket(); sidebarOpen = false">
        <AppIcon name="basket" /> 选号篮
        <span v-if="basketCount" class="nav-count">{{ basketCount }}</span>
      </button>
      <router-link class="nav-item" to="/records" @click="sidebarOpen = false"><AppIcon name="list" /> 购买记录</router-link>
      <router-link class="nav-item" to="/prize" @click="sidebarOpen = false"><AppIcon name="trophy" /> 奖金计算</router-link>
      <div class="nav-label">系统</div>
      <router-link class="nav-item" to="/settings" @click="sidebarOpen = false"><AppIcon name="settings" /> 邮件 / 爬取</router-link>
    </aside>

    <main class="main">
      <router-view />
      <div class="page-foot">孙导带你夜夜笙歌 · 个人观测 · 预测仅供娱乐 · 请理性购彩</div>
    </main>

    <nav class="mobile-tabs">
      <router-link class="mobile-tab" to="/"><AppIcon name="home" />首页</router-link>
      <router-link class="mobile-tab" to="/analysis"><AppIcon name="chart" />分析</router-link>
      <router-link class="mobile-tab" to="/predict"><AppIcon name="sparkle" />预测</router-link>
      <router-link class="mobile-tab" to="/records"><AppIcon name="list" />记录</router-link>
      <router-link class="mobile-tab" to="/settings"><AppIcon name="settings" />更多</router-link>
    </nav>

    <PickBasket />
    <AppFeedback />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import AppIcon from './AppIcon.vue'
import AppFeedback from './AppFeedback.vue'
import PickBasket from './PickBasket.vue'
import { toast } from '../composables/feedback'
import { useBasket } from '../composables/useBasket'

const { count: basketCount, show: openBasket } = useBasket()
const sidebarOpen = ref(false)
const syncing = ref(false)
const dataTag = ref('本地')

async function onSync() {
  syncing.value = true
  try {
    const res = await api.crawl()
    dataTag.value = res.errors?.length ? '混合' : '已同步'
    if (res.errors?.length) {
      toast(`${res.message}（${res.errors[0]}）`, 'info', 4000)
    } else {
      toast(res.message || '同步完成', 'ok')
    }
  } catch (e) {
    toast('同步失败：' + e.message, 'error', 4000)
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
