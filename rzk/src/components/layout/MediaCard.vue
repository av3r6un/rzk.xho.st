<template>
  <div class="media_card">
    <div class="media_card-wrapper">
      <div class="media_card-cover">
        <img :src="cover" v-if="cover" class="base_image" :alt="`cover_${id}`"/>
      </div>
      <div class="media_card-info">
        <div class="media_card-name">
          {{ name }}
        </div>
        <div class="media_card-origin">{{ original_name }}, {{ country }}</div>
        <div class="media_card-release">{{ normalDate }}</div>
        <div class="media_card-slogan">{{ slogan }}</div>
        <div class="media_card-genres">
          <span class="genre" v-for="(g, idx) in genres" :key="idx">
            {{ g }}<span v-if="idx < genres.length - 1">, </span>
          </span>
        </div>
        <div class="media_card-description">{{ description }}</div>
      </div>
    </div>
  </div>
</template>
<script>
export default {
  name: 'MediaCard',
  props: {
    id: {
      type: Number,
      required: true,
    },
    name: {
      type: String,
      required: false,
    },
    original_name: {
      type: String,
      reuiqred: false,
    },
    cover: {
      type: String,
      required: false,
    },
    slogan: {
      type: String,
      required: false,
    },
    release: {
      type: Number,
      required: false,
    },
    country: {
      type: String,
      required: false,
    },
    genres: {
      type: Array,
      required: false,
    },
    description: {
      type: String,
      required: false,
    },
  },
  data() {
    return {};
  },
  computed: {
    normalDate() {
      const dt = new Date(this.release * 1000);
      const d = dt.getDate().toString().padStart(2, '0');
      const m = dt.getMonth().toString().padStart(2, '0');
      const y = dt.getFullYear();
      return `${d}.${m}.${y}`;
    },
  },
};
</script>
<style lang="scss" scoped>
.media_card{
  &-cover{
    min-width: 200px;
    border-radius: 8px;
  }
  &-wrapper{
    display: flex;
    gap: 20px;
    padding: 20px;
    border: 1px solid $yellow;
    border-radius: $radius-lg;
    background: rgba($white, .05);
    box-shadow: inset 0px 0px 20px rgba($yellow, .3);
    position: relative;
    &:before{
      position: absolute;
      content: '';
      width: 250px;
      height: 270px;
      border-radius: 50%;
      background: rgba($yellow, .4);
      z-index: -1;
      transform: rotate(45deg);
      filter: blur(32px);
      left: calc(50% - 125px);
      top: calc(50% - 135px);
    }
  }
  &-info{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  &-name{
    font-size: 20px;
    font-weight: 600;
  }
  &-slogan{
    color: rgba($white, .8);
  }
  &-description{
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 9;
    text-align: justify;
    overflow: hidden;
  }
}
</style>
