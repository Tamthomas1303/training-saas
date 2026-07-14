import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import ProgressBar from '../components/ProgressBar'
import StatCard from '../components/StatCard'
import api from '../api/client'

export default function KpiDashboardPage() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/kpi/stats/')
      .then(({ data }) => setStats(data))
      .catch(() => setError('Không tải được thống kê KPI.'))
  }, [])

  if (error) {
    return (
      <AppShell>
        <p style={{ color: 'var(--danger)' }}>{error}</p>
      </AppShell>
    )
  }
  if (!stats) {
    return (
      <AppShell>
        <p className="muted-note">Đang tải...</p>
      </AppShell>
    )
  }

  const topTopics = stats.top_topics || []
  const perRestaurant = stats.per_restaurant || []

  return (
    <AppShell>
      <h2>Thống kê KPI đào tạo</h2>

      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <StatCard label="Tổng số lớp đào tạo" value={stats.total_classes ?? 0} />
        <StatCard label="Tổng lượt tham gia" value={stats.total_joins ?? 0} />
        <StatCard label="TB học viên/lớp" value={stats.avg_per_class ?? 0} />
      </div>

      <h3>Top chủ đề đào tạo nhiều nhất</h3>
      {topTopics.length === 0 && <p className="muted-note">Chưa có dữ liệu.</p>}
      {topTopics.map((t) => {
        const max = topTopics[0].count
        return (
          <div key={t.topic} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span>{t.topic}</span>
              <span>{t.count}</span>
            </div>
            <ProgressBar percent={max ? (t.count / max) * 100 : 0} />
          </div>
        )
      })}

      <h3 style={{ marginTop: 24 }}>Tiến độ KPI theo nhà hàng (tháng này)</h3>
      {perRestaurant.length === 0 && <p className="muted-note">Chưa có buổi đào tạo nào trong tháng.</p>}
      {perRestaurant.map((r) => (
        <div key={r.restaurant_id} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span>{r.restaurant_name || `Nhà hàng #${r.restaurant_id}`}</span>
            <span>
              {r.done}/{r.target}
            </span>
          </div>
          <ProgressBar
            percent={(r.done / r.target) * 100}
            color={r.achieved ? undefined : 'var(--amber)'}
          />
        </div>
      ))}
    </AppShell>
  )
}
