import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function SettingsPage() {
  const [health, setHealth] = useState(null)
  const [settings, setSettings] = useState(null)
  const [error, setError] = useState('')
  const [switching, setSwitching] = useState(false)

  const refresh = () => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setError('获取状态失败：' + e.message))
    api
      .settings()
      .then(setSettings)
      .catch((e) => setError('获取设置失败：' + e.message))
  }

  useEffect(refresh, [])

  const switchProvider = (name) => {
    setSwitching(true)
    api
      .switchProvider(name)
      .then(() => refresh())
      .catch((e) => setError('切换失败：' + e.message))
      .finally(() => setSwitching(false))
  }

  const Row = ({ label, value }) => (
    <div className="py-2 flex justify-between border-b border-slate-100 last:border-0">
      <span className="text-slate-500 text-sm">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )

  const PROVIDER_LABEL = { deepseek: 'DeepSeek', zhipu: '智谱 GLM', dashscope: '阿里通义' }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-2">服务状态</h2>
        {health ? (
          <div>
            <Row label="后端服务" value={health.ok ? '✅ 运行中' : '❌ 异常'} />
            <Row label="环境" value={health.env || '-'} />
            <Row label="版本" value={health.version || '-'} />
          </div>
        ) : (
          <p className="text-sm text-slate-400">{error || '加载中…'}</p>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-2">LLM 供应商（多模型适配）</h2>
        {settings ? (
          <div className="space-y-2">
            {settings.providers.map((p) => (
              <div
                key={p}
                className="flex items-center justify-between border rounded-lg px-3 py-2"
              >
                <span className="text-sm">
                  {PROVIDER_LABEL[p] || p}
                  {p === settings.current && (
                    <span className="ml-2 px-1.5 py-0.5 rounded bg-green-50 text-green-600 text-[10px]">
                      当前
                    </span>
                  )}
                </span>
                {p !== settings.current && (
                  <button
                    onClick={() => switchProvider(p)}
                    disabled={switching}
                    className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                  >
                    切换
                  </button>
                )}
              </div>
            ))}
            <p className="text-xs text-slate-400 pt-1">
              切换即时生效（内存）；重启后恢复 .env 的 LLM_PROVIDER。未配置 Key 的供应商不可用。
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-400">{error || '加载中…'}</p>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-2">IM 接入</h2>
        <Row
          label="钉钉 Stream 机器人"
          value={settings?.dingtalk_configured ? '✅ 已配置' : '⚠️ 未配置（填 .env 后重启）'}
        />
        <Row
          label="企业微信机器人"
          value={settings?.wecom_configured ? '✅ 已配置' : '⚠️ 未配置（填 .env 后重启）'}
        />
        <Row
          label="飞书机器人"
          value={settings?.feishu_configured ? '✅ 已配置' : '⚠️ 未配置（填 .env 后重启）'}
        />
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-2">配置说明</h2>
        <p className="text-sm text-slate-500 leading-relaxed">
          所有配置在 <code className="bg-slate-100 px-1 rounded">backend/.env</code>（模板见
          <code className="bg-slate-100 px-1 rounded">.env.example</code>）：
        </p>
        <ul className="text-sm text-slate-600 mt-2 space-y-1 list-disc list-inside">
          <li><code className="bg-slate-100 px-1 rounded">LLM_PROVIDER</code> — 默认供应商（deepseek / zhipu / dashscope）</li>
          <li><code className="bg-slate-100 px-1 rounded">DEEPSEEK_API_KEY</code> / <code className="bg-slate-100 px-1 rounded">ZHIPU_API_KEY</code> / <code className="bg-slate-100 px-1 rounded">DASHSCOPE_API_KEY</code> — 各家 Key</li>
          <li><code className="bg-slate-100 px-1 rounded">DINGTALK_APP_KEY/SECRET</code> — 钉钉机器人凭证</li>
        </ul>
        <p className="text-xs text-slate-400 mt-3">修改 .env 后需重启后端生效。</p>
      </div>
    </div>
  )
}
