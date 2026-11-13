<template>
  <article class="login">
    <div class="login_wrapper">
      <div class="login_title centered">Авторизация</div>
      <form class="login_form" @submit.prevent="login">
        <UIInput
          type="text"
          autofocus
          required
          placeholder="Имя пользователя"
          v-model="authForm.username" />
        <UIInput
          type="password"
          required
          placeholder="Пароль"
          v-model="authForm.password" />
        <button type="submit" class="btn btn_submit clickable"
          :disabled="$store.getters.loading">Войти</button>
      </form>
    </div>
  </article>
</template>
<script>
import UIInput from '../components/ui/Input.vue';

export default {
  name: 'Login',
  components: { UIInput },
  data() {
    return {
      authForm: {
        username: null,
        password: null,
      },
    };
  },
  methods: {
    async login() {
      try {
        const credentials = { ...this.authForm };
        await this.$store.dispatch('login', credentials);
        await this.$router.push(this.$route.query.from || '/');
      } catch (error) {
        this.loginError = error.response?.status === 401
          ? 'Неверные данные для входа'
          : error.response?.data?.message || 'Не удалось войти';
      }
    },
  },
};
</script>
<style lang="scss" scoped>
.login{
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  &_wrapper{
    color: $white;
    width: 350px;
    margin: 0 auto;
  }
  &_title{
    font-size: 24px;
    font-weight: 600;
  }
  &_form{
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 12px;
  }
}
</style>
