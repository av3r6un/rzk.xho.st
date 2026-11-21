<template>
  <form class="profile_cookies" @submit.prevent="$emit('submit')">
    <Input
      type="text"
      name="Cookies"
      autofocus
      required
      placeholder="key=value; other=value"
      :icon="configured ? 'fa-solid fa-check' : ''"
      :completed="configured"
      v-model="localValue" />
    <p v-if="cookieError" role="alert"
      class="profile_cookies-error">{{ cookieError }}</p>
    <p class="profile_cookies-caption">В целях безопасности сохраненные cookies не отображаются.</p>
    <button type="submit" class="btn btn_submit" :disabled="!canUpdate">Сохранить</button>
  </form>
</template>
<script>
import Input from '../ui/Input.vue';

export default {
  name: 'Cookies',
  emits: ['update:modelValue', 'submit'],
  components: { Input },
  props: {
    modelValue: {
      type: [String, null],
      required: true,
    },
    configured: {
      type: Boolean,
      default: false,
    },
    saving: {
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
    canUpdate() {
      return this.saving;
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
