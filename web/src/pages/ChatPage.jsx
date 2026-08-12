import { useState } from 'react'
import { api } from '../api.js'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [viewer, setViewer] = useState(null)
  const [viewerText, setViewerText] = useState('')
  const [viewerLoading, setViewerLoading] = useState(false)

  function escapeHtml(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
  }

  function highlightText(text, query) {
    if (!text) return ''
    let html = escapeHtml(text)
    const terms = (query || '')
      .split(/[\s，。？！、；：,.!?;:]+/)
      .filter((t) => t.length >= 2)
    terms.forEach((term) => {
      const safe = escapeHtml(term)
      html = html.split(safe).join(`<mark class="bg-yellow-200 rounded px-0.5">${safe}</mark>`)
    })
    return html
  }

  function renderAnswer(text, refs, question) {
    if (!text) return null
    if (!refs || refs.length === 0) return text
    const parts = []
    const pattern = /\[(\d+)\]/g
    let last = 0
    let match
    let key = 0
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > last) parts.push(text.slice(last, match.index))
      const ref = refs[Number(match[1]) - 1]
      if (ref) {
        parts.push(
          <button
            key={key++}
            onClick={() => openSource(ref, question)}
            className="text-blue-600 underline underline-offset-2 font-medium hover:text-blue-800"
            title="查看原文"
          >
            [{match[1]}]
          </button>
        )
      } else {
        parts.push(match[0])
      }
      last = match.index + match[0].length
    }
    if (last < text.length) parts.push(text.slice(last))
    return parts
  }

  async function openSource(ref, question) {
    setViewer({
      name: ref.name,
      chunkIndex: ref.chunk_index ?? 0,
      question,
    })
    setViewerText(ref.text || '')
    setViewerLoading(true)
    try {
      if (ref.doc_id && ref.chunk_index != null) {
        const data = await api.docChunk(ref.doc_id, ref.chunk_index)
        setViewerText(data.text)
      }
    } catch (e) {
      // 文件问答等临时来源没有持久化片段时，保留引用片段
    } finally {
      setViewerLoading(false)
    }
  }

  async function send() {
    const q = input.trim()
    if (!q || busy) return
    const attached = file
    setInput('')
    setFile(null)
    setMessages((m) => [
      ...m,
      { role: 'user', text: q, file: attached?.name },
      { role: 'assistant', text: '', streaming: true },
    ])
    setBusy(true)
    const patchLast = (changes) =>
      setMessages((m) => {
        const next = [...m]
        if (next.length) Object.assign(next[next.length - 1], changes)
        return next
      })
    let answer = ''
    try {
      const res = attached ? await api.chatFileStream(attached, q) : await api.chatStream(q)
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let sep
        while ((sep = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)
          const dataLine = block.split('\n').find((line) => line.startsWith('data:'))
          if (!dataLine) continue
          const eventLine = block.split('\n').find((line) => line.startsWith('event:'))
          const event = eventLine ? eventLine.slice(6).trim() : 'message'
          const data = JSON.parse(dataLine.slice(5).trim())
          if (event === 'token') {
            answer += data.text
            patchLast({ text: answer, streaming: true })
          } else if (event === 'tool') {
            patchLast({ toolNote: '正在调用工具：' + data.name, streaming: true })
          } else if (event === 'done') {
            answer = data.answer || answer
            patchLast({
              text: answer,
              question: q,
              refs: data.references || [],
              refused: data.refused,
              tools: data.tools_used || [],
              streaming: false,
            })
          } else if (event === 'error') {
            throw new Error(data.message || '未知错误')
          }
        }
      }
      patchLast({ text: answer || '（无回复）', streaming: false })
    } catch (e) {
      patchLast({ text: '请求失败：' + e.message, streaming: false })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-6 flex flex-col h-[70vh]">
      <h2 className="font-semibold mb-3">备用聊天（不依赖钉钉，浏览器直接对话）</h2>
      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400 text-center mt-10">
            试试问：员工 001 是哪个部门的？ / 员工每年几天年假？
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              'max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ' +
              (m.role === 'user'
                ? 'ml-auto bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-800')
            }
          >
            {m.role === 'user' && m.file && (
              <div className="text-xs opacity-80 mb-1">📎 {m.file}</div>
            )}
            {m.streaming && !m.text && (
              <div className="text-xs text-slate-400">{m.toolNote || '思考中…'}</div>
            )}
            {m.text && m.refs ? renderAnswer(m.text, m.refs, m.question) : m.text}
            {m.tools && m.tools.length > 0 && (
              <div className="mt-1 text-xs text-blue-600">
                工具：{m.tools.join('、')}
              </div>
            )}
            {m.refs && m.refs.length > 0 && (
              <div className="mt-2 text-xs text-slate-400 border-t border-slate-200 pt-1">
                <span>📎 来源：</span>
                {m.refs
                  .filter(
                    (r, i, arr) =>
                      arr.findIndex(
                        (x) => x.doc_id === r.doc_id && x.chunk_index === r.chunk_index
                      ) === i
                  )
                  .map((r, i) => (
                    <button
                      key={i}
                      onClick={() => openSource(r, m.question)}
                      className="ml-1 text-blue-600 underline underline-offset-2 hover:text-blue-800"
                    >
                      {r.name}
                    </button>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {file && (
        <div className="mb-2 flex items-center justify-between bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-sm text-blue-700">
          <span className="truncate">📎 {file.name}</span>
          <button
            onClick={() => setFile(null)}
            className="ml-3 text-xs text-blue-600 hover:text-blue-800"
          >
            移除
          </button>
        </div>
      )}
      <div className="flex gap-2">
        <label className="shrink-0 cursor-pointer text-xs text-slate-500 hover:text-blue-600">
          选文件
          <input
            type="file"
            accept=".md,.txt,.pdf,.docx"
            className="hidden"
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
        </label>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="输入问题…"
          className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={send}
          disabled={busy}
          className="px-5 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? '思考中…' : '发送'}
        </button>
      </div>
      {viewer && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setViewer(null)}
        >
          <div
            className="w-full max-w-2xl rounded-xl bg-white p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800">原文位置</h3>
                <p className="text-xs text-slate-400 mt-1">
                  {viewer.name} · 第 {viewer.chunkIndex + 1} 段
                </p>
              </div>
              <button
                onClick={() => setViewer(null)}
                className="text-xs text-slate-500 hover:text-slate-800"
              >
                关闭
              </button>
            </div>
            <div className="mt-4 max-h-80 overflow-y-auto rounded-lg border-l-4 border-yellow-400 bg-yellow-50/60 p-4 text-sm leading-relaxed whitespace-pre-wrap">
              {viewerLoading ? (
                <p className="text-slate-400">加载中…</p>
              ) : (
                <span
                  dangerouslySetInnerHTML={{
                    __html: highlightText(viewerText, viewer.question),
                  }}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
