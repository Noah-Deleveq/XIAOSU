const BASE = '/api'

async function req(path, options = {}) {
  const res = await fetch(BASE + path, options)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  health: () => req('/health'),
  docs: () => req('/docs'),
  uploadDoc: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(BASE + '/docs', { method: 'POST', body: fd }).then((r) => r.json())
  },
  deleteDoc: (id) => req(`/docs/${id}`, { method: 'DELETE' }),
  chat: (message, sessionId = 'web-demo') =>
    req('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'web-admin', session_id: sessionId, message }),
    }),
  logs: () => req('/logs'),
}
