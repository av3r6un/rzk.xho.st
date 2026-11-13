import { createStore } from 'vuex';
import router from '../router';
import Auth from '../services/auth.service';

function readStored(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch (_) { return fallback; }
}

function readUser(batch) {
  if (!batch) return null;
  return { uid: batch.uid, email: batch.email, isAdmin: batch.roles?.includes('admin') ?? false };
}

export default createStore({
  state: {
    authSession: readStored('__localAuthSession', null),
    loading: false,
    error: null,
  },
  getters: {
    isAuth: (state) => Boolean(state.authSession),
    accessToken: (state) => state.authSession?.access_token,
    refreshToken: (state) => state.authSession?.refresh_token,
    expiresAt: (state) => state.authSession?.access_expires_at,
    user: (state) => readUser(state.authSession),
    loading: (state) => state.loading,
    error: (state) => state.error,
  },
  mutations: {
    setAuthSession(state, session) {
      state.authSession = session;
      localStorage.setItem('__localAuthSession', JSON.stringify(session));
    },
    clearSession(state) {
      state.authSession = null;
      localStorage.removeItem('__localAuthSession');
      localStorage.removeItem('__authSession');
    },
    updateHistory(state, history) {
      state.user = { ...state.user, history };
      localStorage.setItem('__usr', JSON.stringify(state.user));
    },
    setLoading(state, value) {
      state.loading = value;
    },
    setError(state, error) {
      state.error = error;
    },
  },
  actions: {
    async login({ commit }, creds) {
      commit('setLoading', true);
      try {
        return await Auth.login(creds);
      } finally {
        commit('setLoading', false);
      }
    },
    refresh: () => Auth.refresh(),
    logout({ commit }) {
      commit('clearSession');
      return router.replace('/login');
    },
  },
  modules: {
  },
});
