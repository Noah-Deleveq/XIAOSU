import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function SettingsPage() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setError('获取状态失败：' + e.message))
  }, [])

  const Row = ({ label, value }) => (
    <div className="py-2 flex justify-between border-b border-slate-100 last:border-0">
      <span className="text-slate-500 text-sm">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-2">服务状态</h2>
        {health ? (
          <div>
            <Row label="后端服务" value={health.ok ? '✅ 运行中' : '❌ 异常'} />
            <Row label="环境" value={health.env || '-'} />
            <Row label="版本" value={health.version || '0.1.0'} />
          </div>
        ) : (
          <p className="text-sm text-slate-400">{error || '加载中…'}</p>
        )}
      </div>
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-2">配置说明</h2>
        <p className="text-sm text-slate-500 leading-relaxed">
          所有配置在 <code className="bg-slate-100 px-1 rounded">backend/.env</code> 中：
        </p>
        <ul className="text-sm text-slate-600 mt-2 space-y-1 list-disc list-inside">
          <li><code className="bg-slate-100 px-1 rounded">LLM_API_KEY</code> — 大模型 Key（DeepSeek 等 OpenAI 兼容）</li>
          <li><code className="bg-slate-100 px-1 rounded">DINGTALK_APP_KEY/SECRET</code> — 钉钉机器人凭证</li>
        </ul>
        <p className="text-xs text-slate-400 mt-3">修改 .env 后需重启后端生效。</p>
      </div>
    </div>
  )
}
