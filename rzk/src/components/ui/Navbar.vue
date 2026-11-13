<template>
  <div class="navbar">
    <div class="navbar_title">
      <router-link to="/" class="base_link">
        RZK
      </router-link>
    </div>
    <div class="navbar_nav">
      <div class="navbar_item">
        <router-link to="/profile" class="base_link" v-if="$store.getters.isAuth">
          Профиль
        </router-link>
        <router-link to="/login" class="base_link" v-else>
          Войти
        </router-link>
      </div>
    </div>
  </div>
</template>
<script>
export default {
  name: 'Navbar',
  data() {
    return {};
  },
};
</script>
<style lang="scss" scoped>
.navbar{
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 15px;
  max-width: 1044px;
  margin: 0 auto;
  color: $yellow;
  &_nav{
    display: flex;
    align-items: center;
    justify-content: flex-end;
    width: 100%;
  }
}
</style>
