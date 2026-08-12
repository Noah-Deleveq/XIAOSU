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
  docChunk: (docId, chunkIndex) =>
    req(`/docs/${encodeURIComponent(docId)}/chunk/${encodeURIComponent(chunkIndex)}`),
  deleteDoc: (id) => req(`/docs/${id}`, { method: 'DELETE' }),
  chat: (message, sessionId = 'web-demo') =>
    req('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'web-admin', session_id: sessionId, message }),
    }),
  chatStream: (message, sessionId = 'web-demo') =>
    fetch(BASE + '/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'web-admin', session_id: sessionId, message }),
    }),
  chatFileStream: (file, message, sessionId = 'web-demo') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('question', message)
    fd.append('user_id', 'web-admin')
    fd.append('session_id', sessionId)
    return fetch(BASE + '/chat/file/stream', { method: 'POST', body: fd })
  },
  logs: () => req('/logs'),
  traces: () => req('/traces'),
  settings: () => req('/settings'),
  switchProvider: (name) =>
    req('/settings/provider', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
}
