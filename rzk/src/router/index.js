import { createRouter, createWebHashHistory } from 'vue-router';
import store from '../store';
import HomeView from '../views/HomeView.vue';
import Login from '../views/LoginView.vue';
import Profile from '../views/ProfileView.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: {
      public: true,
    },
  },
  {
    path: '/profile',
    name: 'profile',
    component: Profile,
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  linkExactActiveClass: 'exact-active',
  linkActiveClass: 'active',
});

router.beforeEach(async (to) => {
  if (!to.meta.public && !store.getters.isAuth) {
    return { path: '/login', query: { from: to.fullPath } };
  }
  if (!to.meta.public) {
    if (!store.getters.isAuth) {
      return { path: '/login', query: { from: to.fullPath } };
    }
  }
  return true;
});

export default router;
