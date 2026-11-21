<template>
  <article class="profile page">
    <div class="profile_title centered">Настройки</div>
    <div class="profile_section">
      <Cookies v-model="settings.cookies.value" :configured="settings.cookies.configured"
        :saving="canUpdateCookies" @submit="updateCookies" />
      <Compression v-model="settings.compression.value" :options="settings.compression.options"
        :saving="saving.compression" @submit="updateCompression" />
      <Encoders v-model="settings.encoders.currentValue" :configured="settings.encoders.present"
        :saving="saving.encoders" @submit="updateEncoders" />
    </div>
  </article>
</template>
<script>
import Backend from '../services/backend.service';
import Cookies from '../components/layout/ProfileCookies.vue';
import Compression from '../components/layout/ProfileCompression.vue';
import Encoders from '../components/layout/ProfileEncoders.vue';

export default {
  name: 'Profile',
  components: { Cookies, Compression, Encoders },
  data() {
    return {
      backend: new Backend(),
      savingCookies: false,
      saving: {
        cookies: false,
        compression: false,
        encoders: false,
      },
      saveError: '',
      settings: {
        cookies: {
          value: null,
          configured: false,
        },
        compression: {
          value: null,
          options: [
            { id: 0, name: 'Качество' },
            { id: 1, name: 'Память' },
            { id: 2, name: 'Баланс' },
          ],
        },
        encoders: {
          currentValue: null,
          present: [],
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
    getEncoders() {
      this.backend.get('/ffmpeg/encoders')
        .then((resp) => { this.settings.encoders.present = resp; })
        .catch((err) => { this.encError = err; });
    },
    updateCompression() {},
    updateEncoders() {},
  },
  computed: {
    cookieHeader() {
      const cookiePair = /^[!#$%&'*+\-.^_\x60|~0-9A-Za-z]+=(?:[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*|"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*")(?![\s\S])/;
      const value = this.settings.cookies.value || '';
      if (value.length > 8192) return '';
      const pairs = value.split(';').map((pair) => pair.replace(/^[ \t]+|[ \t]+$/g, ''));
      if (pairs.length > 1 && pairs[pairs.length - 1] === '') pairs.pop();
      if (!pairs.every((pair) => cookiePair.test(pair))) return '';
      const header = pairs.join('; ');
      return header.length <= 8192 ? header : '';
    },
    canUpdateCookies() {
      return Boolean(this.cookieHeader) && !this.savingCookies;
    },
  },
  beforeMount() {
    this.getCookieState();
    this.getEncoders();
  },
};
</script>
<style lang="scss" scoped>
.profile{
  &_title{
    font-weight: 600;
    font-size: 24px;
  }
  &_section{
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
}
</style>
