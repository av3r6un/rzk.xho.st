<template>
  <div class="search_form">
    <form class="form" @submit.prevent="$emit('search')">
      <Input
        type="text"
        required
        name="Ссылка"
        placeholder="https://hdrezka.ag/"
        autofocus
        :completed="!showButton"
        v-model="localValue" />
      <button type="submit" class="btn btn_submit" v-if="showButton">Поиск</button>
    </form>
  </div>
</template>
<script>
import Input from '../ui/Input.vue';

export default {
  name: 'SearchForm',
  components: { Input },
  emits: ['update:modelValue', 'search'],
  props: {
    modelValue: {
      type: String,
      required: true,
    },
    showButton: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    localValue: {
      get() { return this.modelValue; },
      set(val) { this.$emit('update:modelValue', val); },
    },
  },
};
</script>
<style lang="scss" scoped>
.search_form{
  width: 100%;
  .form{
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 15px;
  }
}
</style>
