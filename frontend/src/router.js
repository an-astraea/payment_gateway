import { createRouter, createWebHistory } from 'vue-router'
import BookView from './views/BookView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/book' },
    { path: '/book', component: BookView, meta: { title: 'Book a consultation' } },
    { path: '/manage/:token', component: () => import('./views/ManageView.vue'), meta: { title: 'Manage your booking' } },
    // Admin has no login yet; protect this route when authentication is added.
    { path: '/admin', component: () => import('./views/AdminView.vue'), meta: { title: 'Consultations dashboard' } },
  ],
})
