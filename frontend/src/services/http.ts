import axios from 'axios'

const http = axios.create({
  withCredentials: true,
})

http.interceptors.request.use((config) => {
  if (config.method && config.method.toUpperCase() !== 'GET') {
    const token = getCookie('csrf_token')
    if (token) {
      config.headers['X-CSRF-Token'] = token
    }
  }
  return config
})

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? decodeURIComponent(match[2]) : null
}

export default http

