import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function LogsPage() {
  const [data, setData] = useState({ logs: [], summary: {} })
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .logs()
      .then(setData)
      .catch((e) => setError('获取日志失败：' + e.message))
  }, [])

  const logs = data.logs || []
  const summary = data.summary || {}

  const fmtCost = (c) => (c == null ? '-' : '¥' + Number(c).toFixed(4))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-slate-400">对话轮次</p>
          <p className="text-2xl font-bold mt-1">{summary.turns ?? logs.length}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-slate-400">总 Token</p>
          <p className="text-2xl font-bold mt-1">{(summary.total_tokens ?? 0).toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-slate-400">估算成本</p>
          <p className="text-2xl font-bold mt-1">{fmtCost(summary.total_cost)}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-3">对话日志（{logs.length} 轮）</h2>
        {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
        {logs.length === 0 ? (
          <p className="text-sm text-slate-400">暂无对话记录。</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-200">
                <th className="py-2 pr-4">时间</th>
                <th className="py-2 pr-4">用户</th>
                <th className="py-2 pr-4">问题</th>
                <th className="py-2 pr-4">回答</th>
                <th className="py-2 pr-4">工具</th>
                <th className="py-2 pr-4">Token</th>
                <th className="py-2">成本</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map((l, i) => (
                <tr key={i}>
                  <td className="py-2 pr-4 text-xs text-slate-400 whitespace-nowrap">{l.ts}</td>
                  <td className="py-2 pr-4 text-xs">{l.user_id}</td>
                  <td className="py-2 pr-4 text-xs text-slate-700 max-w-[160px]">{l.question}</td>
                  <td className="py-2 pr-4 text-xs text-slate-600 max-w-[220px] truncate" title={l.answer}>
                    {l.answer}
                    {l.refused && (
                      <span className="ml-2 px-1.5 py-0.5 rounded bg-red-50 text-red-500 text-[10px]">拒答</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-xs">
                    {l.used_tool ? (
                      <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">
                        {(l.tools_used || ['工具']).join(', ')}
                      </span>
                    ) : (
                      <span className="text-slate-300">-</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-xs text-slate-500">
                    {(l.total_tokens ?? 0).toLocaleString()}
                  </td>
                  <td className="py-2 text-xs text-slate-500">{fmtCost(l.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
