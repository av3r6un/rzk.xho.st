<template>
  <article class="profile page">
    <div class="profile_title centered">Настройки</div>
    <form class="profile_form" @submit.prevent="updateCookies">
      <Input
        type="text"
        name="Cookies"
        autofocus
        required
        placeholder="key=value; other=value"
        :icon="settings.cookies.configured ? 'fa-solid fa-check' : ''"
        v-model="settings.cookies.value"/>
      <p v-if="cookieError || saveError" role="alert"
        class="profile_error">{{ cookieError || saveError }}</p>
      <p class="profile_caption">В целях безопасности сохраненные cookies не отображаются.</p>
      <button type="submit" class="btn btn_submit" :disabled="!canUpdateCookies">Сохранить</button>
    </form>
  </article>
</template>
<script>
import Backend from '../services/backend.service';
import Input from '../components/ui/Input.vue';

// Match the backend's Cookie header format.
const cookiePair = /^[!#$%&'*+\-.^_\x60|~0-9A-Za-z]+=(?:[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*|"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*")(?![\s\S])/;

export default {
  name: 'Profile',
  components: { Input },
  data() {
    return {
      backend: new Backend(),
      savingCookies: false,
      saveError: '',
      settings: {
        cookies: {
          value: null,
          configured: false,
        },
      },
    };
  },
  methods: {
    getCookieState() {
      this.backend.get('/rezka/cookies')
        .then((resp) => { this.settings.cookies.configured = resp.configured; })
        .catch(() => { this.saveError = 'Не удалось загрузить состояние cookies.'; });
    },
    async updateCookies() {
      if (!this.canUpdateCookies) return;
      this.savingCookies = true;
      this.saveError = '';
      try {
        const { configured } = await this.backend.put('/rezka/cookies', {
          cookies: this.cookieHeader,
        });
        this.settings.cookies.configured = configured;
        this.settings.cookies.value = null;
      } catch (_) {
        this.saveError = 'Не удалось сохранить cookies.';
      } finally {
        this.savingCookies = false;
      }
    },
  },
  computed: {
    cookieHeader() {
      const value = this.settings.cookies.value || '';
      if (value.length > 8192) return '';
      const pairs = value.split(';').map((pair) => pair.replace(/^[ \t]+|[ \t]+$/g, ''));
      if (pairs.length > 1 && pairs[pairs.length - 1] === '') pairs.pop();
      if (!pairs.every((pair) => cookiePair.test(pair))) return '';
      const header = pairs.join('; ');
      return header.length <= 8192 ? header : '';
    },
    cookieError() {
      if (!this.settings.cookies.value || this.cookieHeader) return '';
      return 'Введите cookies в формате key=value; other=value (до 8192 символов).';
    },
    canUpdateCookies() {
      return Boolean(this.cookieHeader) && !this.savingCookies;
    },
  },
  beforeMount() {
    this.getCookieState();
  },
};
</script>
<style lang="scss" scoped>
.profile{
  &_title{
    font-weight: 600;
    font-size: 24px;
  }
  &_form{
    max-width: 350px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  &_error,
  &_caption{
    color: rgba($white, .6);
    font-size: 14px;
  }
}
</style>
