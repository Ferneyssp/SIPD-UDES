import axios from "axios";
import { tokenStorage } from "./tokenStorage";

export const API_URL = import.meta.env.VITE_API_URL || "/api";

// X-Requested-With: el backend lo exige en las rutas que usan la cookie de sesión (anti-CSRF).
const SESSION_HEADERS = { "X-Requested-With": "XMLHttpRequest" };
const apiClient = axios.create({ baseURL: API_URL, timeout: 30000, withCredentials: true, headers: SESSION_HEADERS });

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

/** Pide un access token nuevo usando la cookie HttpOnly (el refresh token nunca pasa por JavaScript). */
export async function refreshAccessToken() {
  refreshPromise = refreshPromise || axios
    .post(`${API_URL}/auth/refresh/`, null, { withCredentials: true, headers: SESSION_HEADERS })
    .then(({ data }) => {
      tokenStorage.updateTokens(data);
      return data.access;
    })
    .finally(() => { refreshPromise = null; });
  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isAuthCall = original?.url?.includes("/auth/login") || original?.url?.includes("/auth/refresh");
    if (status === 401 && original && !original._retry && !isAuthCall && tokenStorage.hasSession()) {
      original._retry = true;
      try {
        const access = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${access}`;
        return apiClient(original);
      } catch (refreshError) {
        tokenStorage.clear();
        sessionExpiredHandler();
        return Promise.reject(refreshError);
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
