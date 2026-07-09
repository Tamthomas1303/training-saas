import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let pendingRequests = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    if (response?.status !== 401 || config._retried) {
      return Promise.reject(error)
    }

    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      return Promise.reject(error)
    }

    config._retried = true

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push({ resolve, reject, config })
      })
    }

    isRefreshing = true
    try {
      const { data } = await axios.post(`${BASE_URL}/auth/login/refresh/`, {
        refresh: refreshToken,
      })
      localStorage.setItem('access_token', data.access)
      pendingRequests.forEach(({ resolve, config: pendingConfig }) => {
        pendingConfig.headers.Authorization = `Bearer ${data.access}`
        resolve(api(pendingConfig))
      })
      pendingRequests = []
      config.headers.Authorization = `Bearer ${data.access}`
      return api(config)
    } catch (refreshError) {
      pendingRequests.forEach(({ reject: rejectPending }) => rejectPending(refreshError))
      pendingRequests = []
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)

export default api
