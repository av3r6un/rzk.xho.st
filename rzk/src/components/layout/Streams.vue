<template>
  <article class="streams">
    <div class="streams_row">
      <Selection :options="videos" v-model="selectedQuality"
        placeholder="Выберите качество" name="Качество" v-if="streams?.streams"/>
      <Selection v-model="selectedSubtitles" :options="subtitles"
        placeholder="Выберите язык" name="Субтитры" v-if="pickSubs && streams?.streams?.length" />
    </div>
  </article>
</template>
<script>
import Selection from '../ui/Selection.vue';

export default {
  name: 'Streams',
  components: { Selection },
  emits: ['update:modelValue'],
  props: {
    modelValue: {
      type: [Object, null],
      required: true,
    },
    streams: {
      type: Object,
      required: true,
    },
    pickSubs: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      selectedQuality: null,
      selectedSubtitles: null,
    };
  },
  computed: {
    videos() {
      return (this.streams?.streams ?? []).map(({ uid, title }) => ({ id: uid, title }));
    },
    subtitles() {
      return [
        { id: 0, title: 'Отключить' },
        ...(this.streams?.subtitles ?? []).map(({ uid, title }) => ({ id: uid, title })),
      ];
    },
    selectedSources() {
      if (!this.videos.some(({ id }) => id === this.selectedQuality)) return null;
      if (this.pickSubs && !this.subtitles.some(({ id }) => id === this.selectedSubtitles)) {
        return null;
      }
      return {
        video_uid: this.selectedQuality,
        subtitles_uid: this.pickSubs ? this.selectedSubtitles || null : null,
      };
    },
  },
  watch: {
    selectedSources(form) {
      this.$emit('update:modelValue', form);
    },
  },
};
</script>
<style lang="scss" scoped>
.streams{
  &_row{
    display: flex;
    gap: 20px;
  }
}
</style>
