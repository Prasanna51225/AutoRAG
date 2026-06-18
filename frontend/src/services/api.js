import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

export async function sendQuery(query) {
  const response = await api.post('/query', { query })
  return response.data
}

export async function uploadFile(file, onProgress) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await axios.post(`${API_BASE}/ingest`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percent = (progressEvent.loaded / progressEvent.total) * 100
        onProgress(Math.round(percent))
      }
    },
  })
  return response.data
}

export async function getIngestionStatus(taskId) {
  const response = await api.get(`/ingest/${taskId}`)
  return response.data
}

export async function healthCheck() {
  const response = await api.get('/health')
  return response.data
}
