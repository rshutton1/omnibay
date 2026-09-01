import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  // Hash history: GitHub Pages serves static files and cannot rewrite deep
  // links to index.html, so /mechlab/hbk-4g would 404 on a hard refresh.
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/mechs' },
    {
      path: '/mechs',
      name: 'browser',
      component: () => import('@/views/MechBrowser.vue'),
    },
    {
      path: '/mechlab/:reference',
      name: 'mechlab',
      component: () => import('@/views/MechLab.vue'),
      props: true,
    },
    {
      path: '/skills/:reference',
      name: 'skills',
      component: () => import('@/views/SkillTree.vue'),
      props: true,
    },
    {
      path: '/info/:reference',
      name: 'info',
      component: () => import('@/views/MechInfo.vue'),
      props: true,
    },
  ],
})
