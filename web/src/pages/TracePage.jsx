import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function TracePage() {
  const [traces, setTraces] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .traces()
      .then((r) => setTraces(r.traces || []))
      .catch((e) => setError('获取链路数据失败：' + e.message))
  }, [])

  const failed = traces.filter((t) => t.status === 'error').length
  const totalTokens = traces.reduce((s, t) => s + (t.total_tokens || 0), 0)
  const avgMs = traces.length
    ? Math.round(traces.reduce((s, t) => s + (t.duration_ms || 0), 0) / traces.length)
    : 0

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-slate-400">请求数</p>
          <p className="text-2xl font-bold mt-1">{traces.length}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-slate-400">平均耗时</p>
          <p className="text-2xl font-bold mt-1">{avgMs} ms</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-slate-400">失败 / Token</p>
          <p className="text-2xl font-bold mt-1">
            {failed} / {totalTokens.toLocaleString()}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-3">请求链路</h2>
        {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
        {traces.length === 0 ? (
          <p className="text-sm text-slate-400">暂无请求记录，去聊两句吧。</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-200">
                <th className="py-2 pr-4">时间</th>
                <th className="py-2 pr-4">类型</th>
                <th className="py-2 pr-4">用户</th>
                <th className="py-2 pr-4">状态</th>
                <th className="py-2 pr-4">耗时</th>
                <th className="py-2 pr-4">Token</th>
                <th className="py-2 pr-4">工具</th>
                <th className="py-2">错误</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {traces.map((t) => (
                <tr key={t.id}>
                  <td className="py-2 pr-4 text-xs text-slate-400 whitespace-nowrap">{t.ts}</td>
                  <td className="py-2 pr-4 text-xs">{t.request_type}</td>
                  <td className="py-2 pr-4 text-xs">{t.user_id || '-'}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        'px-1.5 py-0.5 rounded text-[10px] ' +
                        (t.status === 'error'
                          ? 'bg-red-50 text-red-500'
                          : 'bg-green-50 text-green-600')
                      }
                    >
                      {t.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-xs">{t.duration_ms} ms</td>
                  <td className="py-2 pr-4 text-xs">{(t.total_tokens || 0).toLocaleString()}</td>
                  <td className="py-2 pr-4 text-xs">
                    {t.tools_used && t.tools_used.length > 0 ? t.tools_used.join('、') : '-'}
                  </td>
                  <td className="py-2 text-xs text-red-500 max-w-[180px] truncate" title={t.error}>
                    {t.error || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
