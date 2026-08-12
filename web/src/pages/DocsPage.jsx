import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function DocsPage() {
  const [docs, setDocs] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try {
      const r = await api.docs()
      setDocs(r.docs || [])
    } catch (e) {
      setError('获取文档列表失败：' + e.message)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function onUpload(file) {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const r = await api.uploadDoc(file)
      if (!r.ok) setError('上传失败：' + (r.error || ''))
      refresh()
    } catch (e) {
      setError('上传失败：' + e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onDelete(id) {
    if (!window.confirm('确定删除该文档？删除后知识库不再命中。')) return
    await api.deleteDoc(id)
    refresh()
  }

  return (
    <div>
      <div className="bg-white rounded-xl shadow-sm p-6 mb-4">
        <h2 className="font-semibold mb-3">上传文档</h2>
        <label className="block">
          <input
            type="file"
            accept=".md,.txt,.pdf,.docx,.doc"
            onChange={(e) => onUpload(e.target.files[0])}
            disabled={busy}
            className="block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 file:font-medium hover:file:bg-blue-100"
          />
        </label>
        <p className="text-xs text-slate-400 mt-2">支持 Markdown / TXT / PDF / Word，上传后自动解析并建立索引，可在钉钉或下方聊天中提问。</p>
        {busy && <p className="text-sm text-blue-600 mt-2">解析中…</p>}
        {error && <p className="text-sm text-red-500 mt-2">{error}</p>}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-3">知识库文档（{docs.length}）</h2>
        {docs.length === 0 ? (
          <p className="text-sm text-slate-400">还没有文档，上传一份试试。</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {docs.map((d) => (
              <li key={d.id} className="py-3 flex items-center justify-between">
                <div>
                  <p className="font-medium text-slate-800">{d.name}</p>
                  <p className="text-xs text-slate-400">
                    {d.status || 'pending'} · {d.updated_at || ''}
                  </p>
                </div>
                <button
                  onClick={() => onDelete(d.id)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
