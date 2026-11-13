import api from './axios.service';
import store from '../store';
import Auth from './auth.service';

/* eslint-disable */

function isAccessExpired(token) {
  if (!token) return true;
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const { exp } = JSON.parse(atob(payload));
    return typeof exp === 'number' && exp * 1000 <= Date.now();
  } catch (_) {
    return false;
  }
}

api.interceptors.request.use(
  async (config) => {
    const { headers } = config;
    if (!config.authRetried && store.state.authSession && isAccessExpired(store.getters.accessToken)) {
      await Auth.refresh();
    }
    config.authRefreshToken = store.getters.refreshToken;
    if (store.getters.accessToken) headers.Authorization = `Bearer ${store.getters.accessToken}`;
    return config;
  },
  (err) => Promise.reject(err),
);

api.interceptors.response.use(undefined, async (error) => {
  const { config, response } = error;
  const session = store.state.authSession;
  if (response?.status !== 401 || !config || config.authRetried || !session
      || config.authRefreshToken !== session.refresh_token) throw error;
  config.authRetried = true;

  if (config.headers.Authorization === `Bearer ${session.access_token}`) {
    await Auth.refresh();
  }
  if (store.getters.refreshToken !== session.refresh_token) throw error;
  return api(config);
});

class Backend {
  msg = null;
  
  status = 'error';
  
  manageResp({ data }) {
    let body = null;
    if (data?.status === 'success') {
      body = data.body;
    }
    this.msg = body?.message ?? null;
    this.status = body?.status ?? 'error';
    return body;
  }
  
  manageError(err) {
    const status = err?.response?.status;
    const envelope = err?.response?.data?.data;
    this.msg = envelope?.message ?? err?.message ?? 'Request failed';
    if (status >= 400 && status <= 500) {
      this.msg = status === 500 ? 'Server error' : this.msg;
      return Promise.reject(err);
    }
    store.commit('setError', err);
    return Promise.resolve(err);
  }

  async get(url, params) {
    store.commit('setLoading', true);
    store.commit('setError', null);
    return api
      .get(url, { params })
      .then((resp) => this.manageResp(resp))
      .catch((err) => this.manageError(err))
      .finally(() => store.commit('setLoading', false))
  }

  async post(url, data) {
    store.commit('setLoading', true);
    store.commit('setError', null);
    return api
      .post(url, { data: data })
      .then((resp) => this.manageResp(resp))
      .catch((err) => this.manageError(err))
      .finally(() => store.commit('setLoading', false));
  }

  async send(url, file) {
    const data = new FormData();
    data.append('file', file);
    store.commit('setLoading', true);
    store.commit('setError', null);

    return api
      .post(url, data)
      .then((resp) => this.manageResp(resp))
      .catch((err) => this.manageError(err))
      .finally(() => store.commit('setLoading', false));
  }

  async options(url) {
    store.commit('setLoading', true);
    store.commit('setError', null);

    return api
      .options(url)
      .then((resp) => this.manageResp(resp))
      .catch((err) => this.manageError(err))
      .finally(() => store.commit('setLoading', false));
  }

  async put(url, data) {
    store.commit('setLoading', true);
    store.commit('setError', null);
    return api
      .put(url, { data })
      .then((resp) => this.manageResp(resp))
      .catch((err) => this.manageError(err))
      .finally(() => store.commit('setLoading', false));
  }

  async patch(url, data) {
    store.commit('setLoading', true);
    store.commit('setError', null);
    return api
      .patch(url, { data })
      .then((resp) => this.manageResp(resp))
      .catch((err) => this.manageError(err))
      .finally(() => store.commit('setLoading', false));
  }
}

export default Backend;
