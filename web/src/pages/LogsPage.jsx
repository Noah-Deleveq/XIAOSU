import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function LogsPage() {
  const [logs, setLogs] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .logs()
      .then((r) => setLogs(r.logs || []))
      .catch((e) => setError('获取日志失败：' + e.message))
  }, [])

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <h2 className="font-semibold mb-3">对话日志（{logs.length} 条）</h2>
      {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
      {logs.length === 0 ? (
        <p className="text-sm text-slate-400">暂无对话记录。</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-200">
              <th className="py-2 pr-4">时间</th>
              <th className="py-2 pr-4">用户</th>
              <th className="py-2 pr-4">会话</th>
              <th className="py-2 pr-4">角色</th>
              <th className="py-2">内容</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.map((l, i) => (
              <tr key={i}>
                <td className="py-2 pr-4 text-xs text-slate-400 whitespace-nowrap">{l.ts}</td>
                <td className="py-2 pr-4 text-xs">{l.user_id}</td>
                <td className="py-2 pr-4 text-xs text-slate-500">{l.session_id}</td>
                <td className="py-2 pr-4 text-xs">
                  <span
                    className={
                      'px-2 py-0.5 rounded-full text-xs ' +
                      (l.role === 'user' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600')
                    }
                  >
                    {l.role === 'user' ? '用户' : '小苏'}
                  </span>
                </td>
                <td className="py-2 text-xs text-slate-600 max-w-md truncate">{l.content}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
