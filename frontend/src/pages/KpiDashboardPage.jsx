import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar'
import api from '../api/client'
import * as s from './listPageStyles'

function Bar({ percent, color }) {
  return (
    <div style={{ background: '#eee', borderRadius: 4, height: 10, overflow: 'hidden' }}>
      <div style={{ width: `${Math.min(100, Math.max(0, percent))}%`, background: color, height: '100%' }} />
    </div>
  )
}

export default function KpiDashboardPage() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/kpi/stats/')
      .then(({ data }) => setStats(data))
      .catch(() => setError('Không tải được thống kê KPI.'))
  }, [])

  if (error) return <div style={s.page}><NavBar /><p style={{ color: 'red' }}>{error}</p></div>
  if (!stats) return <div style={s.page}><NavBar /><p>Đang tải...</p></div>

  const topTopics = stats.top_topics || []
  const perRestaurant = stats.per_restaurant || []
  const maxTopicCount = topTopics.length ? topTopics[0].count : 0

  return (
    <div style={s.page}>
      <NavBar />
      <h2>Thống kê KPI đào tạo</h2>

      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div style={{ border: '1px solid #eee', borderRadius: 6, padding: 12, minWidth: 160, textAlign: 'center' }}>
          <div style={{ fontSize: 12, color: '#666' }}>Tổng số lớp đào tạo</div>
          <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.total_classes ?? 0}</div>
        </div>
        <div style={{ border: '1px solid #eee', borderRadius: 6, padding: 12, minWidth: 160, textAlign: 'center' }}>
          <div style={{ fontSize: 12, color: '#666' }}>Tổng lượt tham gia</div>
          <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.total_joins ?? 0}</div>
        </div>
        <div style={{ border: '1px solid #eee', borderRadius: 6, padding: 12, minWidth: 160, textAlign: 'center' }}>
          <div style={{ fontSize: 12, color: '#666' }}>TB học viên/lớp</div>
          <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.avg_per_class ?? 0}</div>
        </div>
      </div>

      <h3>Top chủ đề đào tạo nhiều nhất</h3>
      {topTopics.length === 0 && <p style={{ color: '#999' }}>Chưa có dữ liệu.</p>}
      {topTopics.map((t) => (
        <div key={t.topic} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span>{t.topic}</span>
            <span>{t.count}</span>
          </div>
          <Bar percent={maxTopicCount ? (t.count / maxTopicCount) * 100 : 0} color="#3b82f6" />
        </div>
      ))}

      <h3 style={{ marginTop: 24 }}>Tiến độ KPI theo nhà hàng (tháng này)</h3>
      {perRestaurant.length === 0 && <p style={{ color: '#999' }}>Chưa có buổi đào tạo nào trong tháng.</p>}
      {perRestaurant.map((r) => (
        <div key={r.restaurant_id} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span>{r.restaurant_name || `Nhà hàng #${r.restaurant_id}`}</span>
            <span>
              {r.done}/{r.target}
            </span>
          </div>
          <Bar percent={(r.done / r.target) * 100} color={r.achieved ? '#1e7a55' : '#f59e0b'} />
        </div>
      ))}
    </div>
  )
}
