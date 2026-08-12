import { useState } from 'react'
import DocsPage from './pages/DocsPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import LogsPage from './pages/LogsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import TracePage from './pages/TracePage.jsx'

const TABS = [
  { key: 'docs', label: '📄 文档管理' },
  { key: 'chat', label: '💬 备用聊天' },
  { key: 'logs', label: '📋 对话日志' },
  { key: 'traces', label: '🔍 可观测性' },
  { key: 'settings', label: '⚙️ 设置' },
]

export default function App() {
  const [tab, setTab] = useState('docs')
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-800">小苏 · AI 助手管理后台</h1>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={
                'px-4 py-2 rounded-lg text-sm font-medium transition ' +
                (tab === t.key
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-600 hover:bg-slate-100')
              }
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="p-6 max-w-5xl mx-auto">
        {tab === 'docs' && <DocsPage />}
        {tab === 'chat' && <ChatPage />}
        {tab === 'logs' && <LogsPage />}
        {tab === 'traces' && <TracePage />}
        {tab === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
