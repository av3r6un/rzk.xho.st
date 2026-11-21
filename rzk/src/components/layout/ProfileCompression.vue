<template>
  <form class="profile_comp" @submit.prevent="$emit('submit')">
    <Selection
      name="Компрессия"
      :options="options"
      v-model="localValue" />
    <p class="profile_comp-error" role="alert" v-if="compError">{{ compError }}</p>
    <button type="submit" class="btn btn_submit" :disabled="!canUpdate">Сохранить</button>
  </form>
</template>
<script>
import Selection from '../ui/Selection.vue';

export default {
  name: 'Compression',
  components: { Selection },
  emits: ['update:modelValue', 'submit'],
  props: {
    modelValue: {
      type: [String, Number, null],
      required: true,
    },
    options: {
      type: Array,
      required: true,
    },
    error: {
      type: String,
      required: false,
    },
    saving: {
      type: Boolean,
      default: false,
    },
  },
  methods: {
  },
  computed: {
    localValue: {
      get() { return this.modelValue; },
      set(value) { this.$emit('update:modelValue', value); },
    },
    compError() {
      return this.error;
    },
    canUpdate() {
      return this.localValue !== '' && this.localValue !== null && !this.saving;
    },
  },
};
</script>
<style lang="scss" scoped>
.profile_comp{
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
