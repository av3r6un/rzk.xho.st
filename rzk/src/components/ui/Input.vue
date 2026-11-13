<template>
  <div class="input" :class="{ completed }">
    <div class="input_name" :class="{ completed }" v-if="name">{{ name }}</div>
    <i :class="icon" class="icon" v-if="icon"></i>
    <input
      v-model="localValue"
      :type="type"
      :placeholder="placeholder"
      :required="required"
      :autocomplete="defAutocomplete"
      :autofocus="autofocus"
      class="input_wide"
      :class="{ completed }"
      ref="mainInput"
    >
  </div>
</template>
<script>
export default {
  name: 'UIInput',
  props: {
    modelValue: {
      type: [String, Number, null],
      required: true,
    },
    type: {
      type: String,
      default: 'text',
    },
    placeholder: {
      type: String,
      default: 'Введите текст',
    },
    required: {
      type: Boolean,
      default: false,
    },
    autocomplete: {
      type: Boolean,
      default: false,
    },
    autofocus: {
      type: Boolean,
      default: false,
    },
    icon: {
      type: String,
      required: false,
    },
    name: {
      type: String,
      required: false,
    },
    completed: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {};
  },
  methods: {
    blur() {
      this.$refs.mainInput.blur();
    },
  },
  computed: {
    defAutocomplete() {
      return this.autocomplete ? 'on' : 'off';
    },
    localValue: {
      get() { return this.modelValue; },
      set(val) { this.$emit('update:modelValue', val); },
    },
    empty() {
      return this.modelValue === null;
    },
  },
};
</script>
<style lang="scss" scoped>
.input{
  border-radius: $radius-md;
  padding: 0 12px;
  background: transparent;
  display: flex;
  align-items: center;
  flex-direction: row-reverse;
  position: relative;
  gap: 12px;
  border: 1px solid $white;
  &.completed{
    border-color: $yellow;
  }
  &_name{
    position: absolute;
    left: 10px;
    top: -10px;
    background: $black;
    padding: 0 5px;
    font-weight: 500;
    font-size: 14px;
    user-select: none;
    color: $white;
    &.completed{
      color: $yellow;
    }
  }
  &_wide{
    width: 100%;
    outline: none;
    border: none;
    height: 35px;
    border-radius: inherit;
    background: transparent;
    color: $white;
    line-height: 20px;
    &.completed{
      color: $yellow;
    }
    &::placeholder{
      font-family: $font;
      font-size: 15px;
      color: rgba($white, .7);
    }
    &:focus{
      &::placeholder{
        visibility: hidden;
      }
    }
  }
}
</style>
