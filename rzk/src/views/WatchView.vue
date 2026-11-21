<template>
  <article class="watch page">
    <div class="watch_player">
      <div id="player" ref="player"></div>
      <button v-if="airPlay" type="button" class="btn airplay_btn"
        :aria-label="airPlayMessage || 'AirPlay'" :title="airPlayMessage || 'AirPlay'"
        @click="airPlay.open()">
        <i class="fa-brands fa-chromecast"></i>
      </button>
    </div>
  </article>
</template>

<script>
import { Playerjs } from '../services/playerjs.service';
import Backend from '../services/backend.service';
import createAirPlay from '../services/airplay.service';

function bindPipSubtitles(container, player, subtitles) {
  const controller = new AbortController();
  const track = document.createElement('track');
  track.kind = 'subtitles';
  const sync = ({ type, info }) => {
    const video = container.querySelector('video');
    if (!video) return;
    const inPip = document.pictureInPictureElement === video
      || video.webkitPresentationMode === 'picture-in-picture';
    container.classList.toggle('watch_in-pip', inPip);
    const language = type === 'subtitle' ? info : player.api('subtitle');
    const selected = inPip && subtitles.find((subtitle) => subtitle.language === language);
    if (selected) {
      if (track.getAttribute('src') !== selected.url) track.src = selected.url;
      track.label = selected.language;
      if (track.parentElement !== video) video.append(track);
      track.track.mode = 'showing';
    } else {
      track.remove();
    }
  };
  ['subtitle', 'enterpictureinpicture', 'leavepictureinpicture', 'webkitpresentationmodechanged']
    .forEach((event) => container.addEventListener(event, sync, {
      capture: true, signal: controller.signal,
    }));
  return () => {
    controller.abort();
    track.remove();
    container.classList.remove('watch_in-pip');
  };
}

export default {
  name: 'Watch',
  data() {
    return {
      playbackToken: null,
      playbackUrl: null,
      backend: new Backend(),
      media: null,
      airPlay: null,
      airPlayMessage: '',
    };
  },
  methods: {
    initPlayer(urls, subtitles = null) {
      const container = this.$refs.player;
      if (!container) return;
      this.stopPipSubtitles?.();
      this.airPlay?.destroy();
      if (!window.MediaSource && window.ManagedMediaSource) {
        window.MediaSource = window.ManagedMediaSource;
      }
      if (this.isSafari) {
        console.log('Safari detected, using ManagedMediaSource');
      }
      this.player = new Playerjs({
        id: 'player',
        file: urls,
        subtitle: subtitles ? subtitles.map((s) => `[${s.language}]${s.url}`).join(',') : '',
        eventstracker: 1,
        eventlisteners: 1,
        title: this.playerTitle,
      });
      if (subtitles?.length) {
        this.stopPipSubtitles = bindPipSubtitles(container, this.player, subtitles);
      }
      this.airPlayMessage = '';
      this.airPlay = createAirPlay(this.player, this.uid, this.$route.query, (message) => {
        this.airPlayMessage = message;
      });
    },
    fetchMedia() {
      this.backend.get(`/media/${this.uid}`)
        .then((resp) => { this.media = resp; this.gatherWatchData(); })
        .catch((error) => console.error('Error fetching playback token:', error));
    },
    gatherWatchData() {
      this.backend.get(`/watch/${this.uid}`, this.$route.query)
        .then((resp) => {
          console.log(resp.streams);
          const formats = resp.streams.map((s) => `[${s.quality}]${s.url}`).join(',');
          this.expires = resp.expires_at;
          this.initPlayer(formats, resp?.subtitles);
        })
        .catch((error) => console.error('Error fetching playback token:', error));
    },
  },
  computed: {
    playerTitle() {
      if (!this.media) return '';
      const { s, e } = this.$route.query;
      return this.media.category === 'series'
        ? `${this.media.name} - ${s} Сезон, ${e} Серия`
        : `${this.media.name} ${new Date(this.media.release_date).getFullYear()}`;
    },
    isSafari() {
      return /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    },
  },
  beforeMount() {
    this.uid = this.$route.params.id;
    this.fetchMedia();
  },
  beforeUnmount() {
    this.stopPipSubtitles?.();
    this.airPlay?.destroy();
  },
};
</script>

<style lang="scss" scoped>
.watch_in-pip :deep(#pjs_player_subtitle) {
  visibility: hidden !important;
}

.watch{
  &_player{
    position: relative;
    .airplay_btn{
      position: absolute;
      top: calc(100% - 35px);
      color: rgba($white, .7);
      left: 15px;
      font-size: 20px;
      cursor: pointer;
    }
  }
}
</style>
