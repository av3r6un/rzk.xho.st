import axios from 'axios';

const api = axios.create({ baseURL: '/auth' });
let sessionStore;
let refreshInFlight;

const bearer = (token) => ({ headers: { Authorization: `Bearer ${token}` } });

export function configureAuth(store) {
  sessionStore = store;
}

export default {
  async login(credentials) {
    const { data } = await api.post('/', { data: credentials });
    sessionStore.commit('setAuthSession', data.body);
    return data.body;
  },

  async refresh() {
    const session = sessionStore.state.authSession;
    if (!session) throw new Error('Session expired');
    if (!session.refresh_token) {
      await sessionStore.dispatch('logout');
      throw new Error('Session expired');
    }
    if (refreshInFlight?.session === session) return refreshInFlight.promise;

    const attempt = { session };
    attempt.promise = api.post('/refresh', null, bearer(session.refresh_token))
      .then(({ data }) => {
        if (sessionStore.state.authSession !== session) throw new Error('Session changed');
        const updated = { ...session, ...data.body };
        sessionStore.commit('setAuthSession', updated);
        return updated;
      })
      .catch(async (error) => {
        if (error.response?.status === 401 && sessionStore.state.authSession === session) {
          await sessionStore.dispatch('logout');
        }
        throw error;
      })
      .finally(() => {
        if (refreshInFlight === attempt) refreshInFlight = null;
      });
    refreshInFlight = attempt;
    return attempt.promise;
  },
};
