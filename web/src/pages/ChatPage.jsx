import { useState } from 'react'
import { api } from '../api.js'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  async function send() {
    const q = input.trim()
    if (!q || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const r = await api.chat(q)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: r.answer,
          refs: r.references || [],
          refused: r.refused,
        },
      ])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: '请求失败：' + e.message }])
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
            {m.text}
            {m.refs && m.refs.length > 0 && (
              <div className="mt-2 text-xs text-slate-400 border-t border-slate-200 pt-1">
                📎 来源：{m.refs.map((r) => r.name).filter((v, i, a) => a.indexOf(v) === i).join('、')}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
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
    </div>
  )
}
