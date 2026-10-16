import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Analysis from '../views/Analysis.vue'
import Predict from '../views/Predict.vue'
import Records from '../views/Records.vue'
import Prize from '../views/Prize.vue'
import Settings from '../views/Settings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/analysis', name: 'analysis', component: Analysis },
    { path: '/predict', name: 'predict', component: Predict },
    { path: '/records', name: 'records', component: Records },
    { path: '/prize', name: 'prize', component: Prize },
    { path: '/settings', name: 'settings', component: Settings },
  ],
})

export default router
