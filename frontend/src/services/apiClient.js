import axios from "axios";
import { tokenStorage } from "./tokenStorage";

export const API_URL = import.meta.env.VITE_API_URL || "/api";

const apiClient = axios.create({ baseURL: API_URL, timeout: 30000 });

let sessionExpiredHandler = () => {};
export function onSessionExpired(handler) {
  sessionExpiredHandler = handler;
}

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Renovación automática del access token (una sola petición de refresh a la vez).
let refreshPromise = null;

async function refreshAccessToken() {
  const refresh = tokenStorage.getRefresh();
  if (!refresh) throw new Error("Sin refresh token");
  const { data } = await axios.post(`${API_URL}/auth/refresh/`, { refresh });
  tokenStorage.updateTokens(data);
  return data.access;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isAuthCall = original?.url?.includes("/auth/login") || original?.url?.includes("/auth/refresh");
    if (status === 401 && original && !original._retry && !isAuthCall && tokenStorage.getRefresh()) {
      original._retry = true;
      try {
        refreshPromise = refreshPromise || refreshAccessToken();
        const access = await refreshPromise;
        original.headers.Authorization = `Bearer ${access}`;
        return apiClient(original);
      } catch (refreshError) {
        tokenStorage.clear();
        sessionExpiredHandler();
        return Promise.reject(refreshError);
      } finally {
        refreshPromise = null;
      }
    }
    if (status === 401 && !isAuthCall) {
      tokenStorage.clear();
      sessionExpiredHandler();
    }
    return Promise.reject(error);
  },
);

export default apiClient;
