<template>
  <div class="select" :class="{ opened, selected: hasValue }" @click="toggle">
    <div class="select_name">{{ name }}</div>
    <div class="select_options" v-show="opened">
      <div class="select_options-scroll">
        <div class="select_option" v-for="(o, idx) in options" :key="idx">
          <div class="option" @click="select(o)">{{ getOptionLabel(o) }}</div>
        </div>
      </div>
    </div>
    <div class="select_default selected" v-if="hasValue">{{ localText }}</div>
    <div class="select_default" v-else>{{ placeholder }}</div>
  </div>
</template>
<script>
export default {
  name: 'Selection',
  emits: ['update:modelValue'],
  props: {
    options: {
      type: Array,
    },
    modelValue: {
      type: [String, Number, null],
      required: true,
    },
    name: {
      type: String,
      required: false,
    },
    placeholder: {
      type: String,
      required: false,
    },
  },
  data() {
    return {
      opened: false,
    };
  },
  computed: {
    localValue: {
      get() { return this.modelValue; },
      set(val) { this.$emit('update:modelValue', val?.uid ?? val?.id ?? val); },
    },
    hasValue() {
      return Boolean(this.localValue) || this.localValue === 0;
    },
    selectedOption() {
      return this.options?.find((o) => {
        if (typeof o === 'string') return o === this.localValue;
        return o.id === this.localValue;
      });
    },
    localText() {
      if (!this.selectedOption) return this.localValue;
      return this.getOptionLabel(this.selectedOption);
    },
  },
  methods: {
    getOptionLabel(option) {
      return typeof option === 'string' ? option : option.name || option.title;
    },
    toggle() {
      this.opened = !this.opened;
    },
    select(o) {
      if (typeof o === 'object') {
        this.localValue = o;
      } else {
        this.localValue = o;
      }
    },
    reset() {
      this.localValue = null;
    },
  },
};
</script>
<style lang="scss" scoped>
.select{
  user-select: none;
  height: 35px;
  border-radius: $radius-md;
  border: 1px solid $white;
  min-width: 120px;
  padding: 5px 12px;
  position: relative;
  background: $black;
  width: 100%;
  &.selected{
    border-color: $yellow;
    .select_default{
      color: $yellow;
      &:after{
        color: rgba($yellow, .8);
      }
    }
    .select_name{
      color: $yellow;
    }
    .select_options{
      border-color: $yellow;
    }
  }
  &_name{
    position: absolute;
    top: -10px;
    left: 10px;
    padding: 0 5px;
    font-size: 14px;
    font-weight: 500;
    background: $black;
  }
  &.opened{
    z-index: 3;
    .select_default:after{
      transform: rotateX(180deg);
      top: calc(50% - 6px);
    }
  }
  &_options{
    position: absolute;
    width: 100%;
    top: 100%;
    left: 0;
    padding: 5px;
    margin-top: 5px;
    box-sizing: border-box;
    border: 1px solid $white;
    border-radius: $radius-md;
    background: $black;
    &-scroll{
      padding: 0 2px;
      max-height: 200px;
      overflow-y: auto;
      &::-webkit-scrollbar{
        width: 4px;
        background: rgba($yellow, .4);
        border-radius: 2px;
        &-thumb{
          background: $white;
          border-radius: inherit;
        }
      }
    }
    .option{
      box-sizing: border-box;
      border-radius: 3px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      background: transparent;
      transition: all .3s ease;
      color: $yellow;
      &:hover{
        background: $yellow;
        color: $black;
      }
    }
  }
  &_default{
    color: $white;
    z-index: 1;
    display: flex;
    align-items: center;
    font-size: 16px;
    height: 100%;
    width: 100%;
    position: relative;
    color: rgba($white, .6);
    &:after{
      position: absolute;
      content: '\f078';
      font-family: 'FontAwesome';
      width: 16px;
      height: 16px;
      top: calc(50% - 9px);
      right: 0;
      color: $white;
      font-size: 16px;
      transition: all .4s ease;
      z-index: 1;
    }
  }
}
</style>
