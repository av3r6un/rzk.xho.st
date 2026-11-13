import { createApp } from 'vue';
import App from './App.vue';
import './registerServiceWorker';
import router from './router';
import store from './store';
import { configureAuth } from './services/auth.service';
import './assets/main.scss';
import '@fortawesome/fontawesome-free/css/all.min.css';

configureAuth(store);

const app = createApp(App);
const clickOutsideHandlers = new WeakMap();

app.directive('click-outside', {
  beforeMount(el, binding) {
    const handler = (event) => {
      if (!(el === event.target || el.contains(event.target))) {
        if (typeof binding.value === 'function') {
          binding.value(event);
        }
      }
    };
    clickOutsideHandlers.set(el, handler);
    document.body.addEventListener('click', handler);
  },
  unmounted(el) {
    const handler = clickOutsideHandlers.get(el);
    if (handler) {
      document.body.removeEventListener('click', handler);
      clickOutsideHandlers.delete(el);
    }
  },
});

app.use(store).use(router).mount('#app');
