<template>
  <div class="home page">
    <div class="home_title centered">Поиск</div>
    <div class="home_wrapper">
      <SearchForm
        v-model="rezkaForm.url"
        :show-button="!canBeContinued"
        @search="fetchRezka" />
      <MediaCard v-bind="rezkaForm" :show-button="canBeContinued" v-if="rezkaForm.id" />
      <div class="home_row" v-if="rezkaForm.seasons?.length">
        <Selection :model-value="downloadForm.season" :options="rezkaForm.seasons"
          @update:model-value="selectSeason"
          placeholder="Выберите сезон" name="Сезон"/>
        <Selection v-model="downloadForm.episode" :options="selectedSeasonEpisodes"
          placeholder="Выберите серию" name="Серия" v-if="selectedSeasonEpisodes.length" />
      </div>
      <Selection v-model="downloadForm.translator_id" :options="rezkaForm.translators"
        placeholder="Дубляж" name="Озвучка" v-if="rezkaForm.translators" />
      <Streams :streams="streams" :pickSubs="selectedOriginalLanguage"
        v-model="sources" :key="streamsVersion"/>
      <button type="button" class="btn btn_submit" @click="postSources" v-if="readySources"
        :disabled="postingSources || preparationSocket !== null">
        {{ sources.subtitles_uid ? 'Подготовить MP4' : 'Скачать' }}
      </button>
      <p v-if="downloadError" role="alert">{{ downloadError }}</p>
      <div v-if="preparation && preparation.phase !== 'ready'" class="home_progress"
        aria-live="polite">
        <p v-if="preparation.phase === 'downloading'" class="home_progress-label">
          Загрузка исходного видео: {{ formatBytes(preparation.received) }}
          <span v-if="preparation.total"> из {{ formatBytes(preparation.total) }}</span>
        </p>
        <p v-else-if="preparation.phase === 'muxing'"
          class="home_progress-label">Добавляем дорожку субтитров…</p>
        <p v-else class="home_progress-label">Подготовка загрузки…</p>
        <progress v-if="preparation.phase === 'downloading'"
          class="home_progress-progress"
          :value="preparation.total ? preparation.received : null"
          :max="preparation.total || 1" aria-label="Загрузка исходного видео" />
        <button type="button" class="btn btn_submit" @click="cancelPreparation">Отменить</button>
      </div>
      <a v-if="preparation?.phase === 'ready'" class="base_link btn btn_ready"
        :href="preparation.url" referrerpolicy="no-referrer" download>
        Скачать готовый MP4
      </a>
      <div v-if="downloadTicket">
        <a :href="downloadTicket.video_url" referrerpolicy="no-referrer">Скачать исходный MP4</a>
        <a :href="downloadTicket.subtitles_url" referrerpolicy="no-referrer">Скачать субтитры</a>
      </div>
    </div>
  </div>
</template>

<script>
import SearchForm from '../components/layout/SearchForm.vue';
import MediaCard from '../components/layout/MediaCard.vue';
import Backend from '../services/backend.service';
import Selection from '../components/ui/Selection.vue';
import Streams from '../components/layout/Streams.vue';

export default {
  name: 'Home',
  components: {
    SearchForm,
    MediaCard,
    Selection,
    Streams,
  },
  emits: ['movie-form-ready', 'episode-form-ready'],
  data() {
    return {
      backend: new Backend(),
      rezkaForm: {
        url: '',
        id: null,
      },
      subtitlesLang: [
        { id: 'eng', title: 'English' },
        { id: 'rus', title: 'Русский' },
        { id: 'none', title: 'Отключить' },
      ],
      downloadForm: {
        season: null,
        episode: null,
        translator_id: null,
      },
      streams: {},
      sources: null,
      streamsVersion: 0,
      postingSources: false,
      downloadTicket: null,
      preparationSocket: null,
      preparation: null,
      downloadError: '',
      buttonText: 'Поиск',
    };
  },
  beforeUnmount() {
    this.cancelPreparation();
  },
  methods: {
    formatBytes(bytes) {
      return `${(bytes / (1024 * 1024)).toLocaleString('ru', { maximumFractionDigits: 1 })} МиБ`;
    },
    cancelPreparation() {
      const socket = this.preparationSocket;
      this.preparationSocket = null;
      this.preparation = null;
      if (socket) socket.close();
    },
    prepareMp4(ticket) {
      const url = new URL(ticket.prepare_url, window.location.href);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(url);
      this.preparationSocket = socket;
      this.preparation = { phase: 'connecting' };
      socket.onmessage = ({ data }) => {
        if (this.preparationSocket !== socket) return;
        const update = JSON.parse(data);
        if (update.phase === 'error') {
          this.downloadError = update.message;
          this.cancelPreparation();
        } else {
          this.preparation = update;
        }
      };
      socket.onclose = () => {
        if (this.preparationSocket !== socket) return;
        this.preparationSocket = null;
        if (this.preparation?.phase !== 'ready') {
          this.preparation = null;
          this.downloadError = 'Подготовка прервалась. Запустите её ещё раз.';
        }
      };
    },
    fetchRezka() {
      const [url, fragment = ''] = this.rezkaForm.url.trim().split('#', 2);
      const selection = Object.fromEntries(
        Array.from(
          fragment.matchAll(/(?:^|-)([tse]):(\d+)(?=-|$)/g),
          ([, key, value]) => [key, Number(value)],
        ),
      );

      return this.backend.post('/rezka/media', { url })
        .then((resp) => {
          if (!resp?.id) return;
          const season = resp.seasons?.find(({ id }) => id === selection.s);
          const episode = season?.episodes?.find(({ id }) => id === selection.e);
          const translator = resp.translators?.find(({ id }) => id === selection.t);
          this.downloadForm = {
            season: season?.id ?? null,
            episode: episode?.id ?? null,
            translator_id: translator?.id ?? (resp.id === this.rezkaForm.id
              ? this.downloadForm.translator_id : null),
          };
          this.rezkaForm = resp;
        });
    },
    selectSeason(season) {
      if (season === this.downloadForm.season) return;
      this.downloadForm.season = season;
      this.downloadForm.episode = null;
    },
    updatingValue(value) {
      console.log(value);
    },
    refreshStreams(form) {
      this.cancelPreparation();
      this.streamsVersion += 1;
      this.streams = {};
      this.sources = null;
      this.downloadTicket = null;
      this.downloadError = '';
      if (form) this.getStreams(form);
    },
    async getStreams(form) {
      const { uid } = this.rezkaForm;
      const version = this.streamsVersion;
      try {
        const result = await this.backend.post(`/rezka/media/${uid}/streams`, form);
        if (version === this.streamsVersion && form === this.readyDownloadForm) {
          this.streams = result?.streams ? result : {};
        }
      } catch {
        if (version === this.streamsVersion) this.downloadError = this.backend.msg;
      }
    },
    async postSources() {
      if (!this.readySources || this.postingSources || this.preparationSocket) return;
      const sources = this.sources;
      const version = this.streamsVersion;
      const { uid } = this.rezkaForm;
      this.cancelPreparation();
      this.postingSources = true;
      this.downloadError = '';
      this.downloadTicket = null;
      try {
        const ticket = await this.backend.post(`/rezka/media/${uid}/downloads`, sources);
        if (version !== this.streamsVersion || sources !== this.sources) return;
        if (!ticket?.video_url) throw new Error('Сервер не вернул ссылку для скачивания');
        if (ticket.subtitles_url) {
          this.downloadTicket = ticket;
          this.prepareMp4(ticket);
        } else {
          window.location.assign(ticket.video_url);
        }
      } catch (error) {
        if (version === this.streamsVersion && sources === this.sources) {
          const status = error.response?.status;
          if (status === 410 || status === 404) {
            this.refreshStreams(this.readyDownloadForm);
            this.downloadError = 'Ссылки обновляются. Выберите качество и субтитры заново.';
          } else {
            this.downloadError = error.response?.data?.data?.message ?? error.message;
          }
        }
      } finally {
        this.postingSources = false;
      }
    },
  },
  watch: {
    sources() {
      this.cancelPreparation();
      this.downloadTicket = null;
    },
    readyDownloadForm: {
      flush: 'post',
      handler(form) {
        this.refreshStreams(form);
      },
    },
  },
  computed: {
    isTV() {
      return this.rezkaForm.category === 'series' || Boolean(this.rezkaForm.seasons?.length);
    },
    readySources() {
      return Boolean(this.readyDownloadForm && this.sources?.video_uid);
    },
    readyDownloadForm() {
      const translatorId = this.downloadForm.translator_id;
      if (!this.rezkaForm.id || !(translatorId > 0)) return null;
      if (!this.isTV) return { translator_id: translatorId };

      const { season, episode } = this.downloadForm;
      if (!(season > 0 && episode > 0)) return null;
      return {
        season, episode, translator_id: translatorId,
      };
    },
    selectedSeasonEpisodes() {
      return this.rezkaForm.seasons?.find(
        (season) => season.id === this.downloadForm.season,
      )?.episodes ?? [];
    },
    canBeContinued() {
      return this.rezkaForm?.id !== null;
    },
    selectedOriginalLanguage() {
      return this.downloadForm.translator_id === 238;
    },
  },
};
</script>
<style lang="scss" scoped>
.home{
  &_wrapper{
    width: 100%;
    max-width: 850px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin: 0 auto;
  }
  &_title{
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 18px;
  }
  &_row{
    display: flex;
    align-items: center;
    gap: 20px;
  }
  &_progress{
    display: flex;
    flex-direction: column;
    max-width: 650px;
    width: 100%;
    margin: 0 auto;
    gap: 20px;
    progress[value]::-webkit-progress-value{
      background-color: $yellow !important;
    }
    padding: 25px;
    border: 1px solid $yellow;
    border-radius: $radius-lg;
  }
}
</style>
