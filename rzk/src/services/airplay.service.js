import api from './axios.service';

export default function createAirPlay(player, mediaUid, params, setMessage) {
  const video = document.createElement('video');
  if (!video.webkitShowPlaybackTargetPicker) return null;

  const controller = new AbortController();
  const { signal } = controller;
  video.preload = 'metadata';
  video.playsInline = true;
  video.setAttribute('aria-hidden', 'true');
  video.setAttribute('x-webkit-airplay', 'allow');
  Object.assign(video.style, {
    position: 'fixed',
    width: '1px',
    height: '1px',
    opacity: '0',
    pointerEvents: 'none',
  });
  document.body.append(video);

  let shareExpiresAt = 0;
  let loadingShare = false;
  let subtitleCount = 0;
  let warmupTimer;
  let resumeLocalPlayback = null;

  function selectSubtitlesWhenReady() {
    const tracks = Array.from(video.textTracks)
      .filter(({ kind }) => kind === 'subtitles' || kind === 'captions');
    if (tracks.length < subtitleCount) return false;
    if (tracks.length && !tracks.some(({ mode }) => mode === 'showing')) {
      const language = player.api('subtitle');
      const selected = tracks.find(({ label }) => label === language) || tracks[0];
      selected.mode = 'showing';
    }
    return true;
  }

  function stopWarmup() {
    if (warmupTimer === undefined) return;
    clearTimeout(warmupTimer);
    warmupTimer = undefined;
    video.pause();
    video.muted = false;
  }

  function startMutedPlayback() {
    if (warmupTimer !== undefined) return;
    setMessage('Готовим субтитры AirPlay…');
    // Safari may expose HLS subtitle tracks only after playback begins.
    video.muted = true;
    const stopWaiting = () => {
      stopWarmup();
      setMessage('Safari ещё не загрузил субтитры. Нажми AirPlay ещё раз.');
    };
    const timer = setTimeout(stopWaiting, 5000);
    warmupTimer = timer;
    video.play().catch(() => {
      if (warmupTimer === timer) stopWaiting();
    });
  }

  function onSubtitleTracksChanged({ type }) {
    if (selectSubtitlesWhenReady()) {
      stopWarmup();
      setMessage('');
    } else if (type === 'loadedmetadata') {
      startMutedPlayback();
    }
  }

  async function loadShare() {
    if (loadingShare) return;
    loadingShare = true;
    try {
      const { data } = await api.get(`/watch/${mediaUid}/share`, { params, signal });
      if (signal.aborted) return;
      const { body } = data;
      if (!body?.url) throw new Error('Missing AirPlay URL');
      subtitleCount = body.subtitle_count ?? 0;
      shareExpiresAt = body.expires_at;
      video.src = body.url;
    } catch {
      if (!signal.aborted) setMessage('Не удалось подготовить поток AirPlay.');
    } finally {
      loadingShare = false;
    }
  }

  async function playOnTV() {
    try {
      selectSubtitlesWhenReady();
      await video.play();
      if (signal.aborted || !video.webkitCurrentPlaybackTargetIsWireless) return;
      if (resumeLocalPlayback === null) {
        resumeLocalPlayback = Boolean(player.api('playing'));
        player.api('pause');
      }
      setMessage('');
    } catch {
      if (!signal.aborted && video.webkitCurrentPlaybackTargetIsWireless) {
        setMessage('Нажми AirPlay ещё раз, чтобы начать воспроизведение.');
      }
    }
  }

  function onPlaybackTargetChanged() {
    if (video.webkitCurrentPlaybackTargetIsWireless) {
      stopWarmup();
      video.currentTime = player.api('time') || 0;
      playOnTV();
      return;
    }
    video.pause();
    if (resumeLocalPlayback === null) return;
    player.api('seek', video.currentTime);
    if (resumeLocalPlayback && !video.ended) player.api('play');
    resumeLocalPlayback = null;
  }

  video.addEventListener('loadedmetadata', onSubtitleTracksChanged, { signal });
  video.textTracks.addEventListener('addtrack', onSubtitleTracksChanged, { signal });
  video.addEventListener('webkitcurrentplaybacktargetiswirelesschanged', onPlaybackTargetChanged, { signal });
  video.addEventListener('error', () => {
    stopWarmup();
    shareExpiresAt = 0;
    setMessage('Не удалось загрузить поток AirPlay.');
  }, { signal });
  loadShare();

  return {
    open() {
      const connected = video.webkitCurrentPlaybackTargetIsWireless;
      if (connected && resumeLocalPlayback === null) {
        playOnTV();
        return;
      }
      if (!connected && Date.now() / 1000 >= shareExpiresAt) {
        setMessage('Готовим AirPlay. Нажми ещё раз, когда поток загрузится.');
        loadShare();
        return;
      }
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
        setMessage('Поток AirPlay ещё загружается.');
        return;
      }
      if (!connected) {
        if (!selectSubtitlesWhenReady()) {
          startMutedPlayback();
          return;
        }
        stopWarmup();
        video.currentTime = player.api('time') || 0;
      }
      video.webkitShowPlaybackTargetPicker();
    },
    destroy() {
      controller.abort();
      stopWarmup();
      video.pause();
      video.removeAttribute('src');
      video.load();
      video.remove();
    },
  };
}
