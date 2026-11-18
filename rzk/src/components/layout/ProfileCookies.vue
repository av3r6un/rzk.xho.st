<template>
  <form class="profile_cookies" @submit.prevent="$emit('submit')">
    <Input
      type="text"
      name="Cookies"
      autofocus
      required
      placeholder="key=value; other=value"
      :icon="configured ? 'fa-solid fa-check' : ''"
      v-model="localValue" />
    <p v-if="cookieError || saveError" role="alert"
      class="profile_cookies-error">{{ cookieError || saveError }}</p>
    <p class="profile_cookies-caption">В целях безопасности сохраненные cookies не отображаются.</p>
    <button type="submit" class="btn btn_submit" :disabled="!canUpdateCookies">Сохранить</button>
  </form>
</template>
<script>
import Input from '../ui/Input.vue';

export default {
  name: 'ProfileCookies',
  emits: ['update:modelValue', 'submit'],
  components: { Input },
  props: {
    modelValue: {
      type: String,
      required: true,
    },
    configured: {
      type: Boolean,
      default: false,
    },
    savingCookies: {
      type: Boolean,
      default: false,
    },
  },
  methods: {},
  computed: {
    localValue: {
      get() { return this.modelValue; },
      set(value) { this.$emit('update:modelValue', value); },
    },
    cookieError() {
      if (!this.localValue) return '';
      return 'Введите cookies в формате key=value; other=value (до 8192 символов).';
    },
  },
};
</script>
<style lang="scss" scoped>
.profile_cookies{
  max-width: 350px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  &-caption,
  &-error{
    color: rgba($white, .6);
    font-size: 14px;
  }
}
</style>
