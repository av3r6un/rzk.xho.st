<template>
  <div class="profile_encoders">
    <div class="profile_encoders-configured">
      <span class="profile_encoders-encoder" v-for="(enc, idx) in configured" :key="idx"
        :title="checkCaption(enc.checked_at)">
        {{ enc.name }}
      </span>
    </div>
    <form class="profile_encoders-form" @submit.prevent="$emit('submit')">
      <Input
        type="text"
        name="Кодек"
        required
        placeholder="libx265"
        v-model="localValue" />
      <p class="profile_encoders-error" v-if="encError">{{ encError }}</p>
      <button type="submit" class="btn btn_submit" :disabled="!canUpdate">Добавить</button>
    </form>
  </div>
</template>
<script>
import Input from '../ui/Input.vue';

export default {
  name: 'Encoders',
  emits: ['update:modelValue', 'submit'],
  components: { Input },
  props: {
    modelValue: {
      type: [String, null],
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
    configured: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      timer: null,
      now: Date.now(),
    };
  },
  methods: {
    checkCaption(timestamp) {
      const relativeTimeFormatter = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' });
      const relativeTimeUnits = [
        ['day', 86_400],
        ['hour', 3_600],
        ['minute', 60],
        ['second', 1],
      ];
      if (!Number.isFinite(timestamp)) return undefined;

      const seconds = timestamp - this.now / 1000;
      const [unit, size] = relativeTimeUnits.find(([, threshold]) => Math.abs(seconds) >= threshold)
        ?? ['second', 1];

      return `Проверено: ${relativeTimeFormatter.format(Math.trunc(seconds / size), unit)}`;
    },
  },
  computed: {
    localValue: {
      get() { return this.modelValue; },
      set(value) { this.$emit('update:modelValue', value); },
    },
    encError() {
      return this.error;
    },
    canUpdate() {
      return this.localValue !== '' && this.localValue !== null && !this.saving;
    },
  },
  mounted() {
    console.log(this.configured);
    this.timer = setInterval(() => { this.now = Date.now(); }, 1000);
  },
  beforeUnmount() {
    clearInterval(this.timer);
  },
};
</script>
<style lang="scss" scoped>
.profile_encoders{
  max-width: 350px;
  &-configured{
    margin-bottom: 12px;
    display: inline-flex;
    gap: 5px;
    flex-wrap: wrap;
  }
  &-encoder{
    background: rgba($white, .2);
    padding: 3px 5px;
    border-radius: 4px;
  }
  &-form{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  &-caption,
  &-error{
    color: rgba($white, .6);
    font-size: 14px;
  }
}
</style>
