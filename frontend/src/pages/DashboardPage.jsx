import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import MiniCalendar from '../components/MiniCalendar'
import ProgressBar from '../components/ProgressBar'
import StatCard from '../components/StatCard'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'

function fmtMoney(n) {
  return `${Math.round(n || 0).toLocaleString('vi-VN')}đ`
}

const RECENT_STATUS_OPTIONS = [
  { value: 'all', label: 'Tất cả' },
  { value: 'in_progress', label: 'Đang đào tạo' },
  { value: 'not_started', label: 'Chưa đào tạo' },
  { value: 'done', label: 'Hoàn thành' },
]

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [recentOrder, setRecentOrder] = useState('oldest')
  const [recentStatus, setRecentStatus] = useState('all')

  useEffect(() => {
    api
      .get('/employees/dashboard/', { params: { recent_order: recentOrder, recent_status: recentStatus } })
      .then(({ data }) => setData(data))
      .catch(() => setError('Không tải được số liệu dashboard.'))
  }, [recentOrder, recentStatus])

  return (
    <AppShell>
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, var(--forest), var(--green))',
          color: '#fff',
          border: 'none',
          marginBottom: 16,
        }}
      >
        <h2 style={{ color: '#fff', margin: 0 }}>Xin chào, {user.full_name || user.username}</h2>
        <p style={{ margin: '8px 0 0', opacity: 0.9 }}>
          {user.tenant_name} · Vai trò: {user.role}
        </p>
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!error && !data && <p className="muted-note">Đang tải...</p>}

      {data && (
        <>
          <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
            <StatCard label="Tổng nhân viên mới (tháng này)" value={data.stats.total_new}>
              {data.stats.total_new_delta != null && (
                <div className="muted-note" style={{ marginTop: 4 }}>
                  {data.stats.total_new_delta >= 0 ? '+' : ''}
                  {data.stats.total_new_delta}% so với tháng trước
                </div>
              )}
            </StatCard>
            <StatCard label="Tỷ lệ đạt thử việc" value={`${data.stats.pass_rate}%`}>
              <ProgressBar percent={data.stats.pass_rate} />
            </StatCard>
            <StatCard label="Đang thử việc" value={data.stats.probation} />
            <StatCard label="Chi phí phụ cấp trainer" amber value={fmtMoney(data.allowance_cost)} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, alignItems: 'start' }}>
            <div>
              <div className="card" style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <h3 style={{ margin: 0 }}>Tiến độ đào tạo nhân sự mới</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <Link to="/employees" style={{ fontSize: 13 }}>
                      Xem tất cả
                    </Link>
                    <span className="muted-note">·</span>
                    <button
                      className={`btn-sm ${recentOrder === 'oldest' ? '' : 'btn-outline'}`}
                      onClick={() => setRecentOrder('oldest')}
                    >
                      Cũ nhất
                    </button>
                    <button
                      className={`btn-sm ${recentOrder === 'newest' ? '' : 'btn-outline'}`}
                      onClick={() => setRecentOrder('newest')}
                    >
                      Mới nhất
                    </button>
                    {RECENT_STATUS_OPTIONS.map((o) => (
                      <button
                        key={o.value}
                        className={`btn-sm ${recentStatus === o.value ? '' : 'btn-outline'}`}
                        onClick={() => setRecentStatus(o.value)}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
                {data.recent.length === 0 && <p className="muted-note">Chưa có dữ liệu.</p>}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 12 }}>
                  {data.recent.map((r) => (
                    <div key={r.employee_id} style={{ border: '1px solid var(--card-border)', borderRadius: 10, padding: 10 }}>
                      <div style={{ fontWeight: 600 }}>{r.name}</div>
                      <div className="muted-note" style={{ fontSize: 12, marginBottom: 6 }}>
                        {r.code} · {r.position}
                      </div>
                      <ProgressBar percent={r.progress} />
                      <div className="muted-note" style={{ fontSize: 12, marginTop: 4 }}>{r.progress}%</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ marginBottom: 16 }}>
                <h3 style={{ marginTop: 0 }}>
                  Tỷ lệ hoàn thành thử việc ≤15 ngày (cấp S)
                </h3>
                <div className="stat-num">{data.prob15.rate}%</div>
                <ProgressBar percent={data.prob15.rate} />
                <div className="muted-note" style={{ marginTop: 4 }}>
                  {data.prob15.num}/{data.prob15.den} nhân sự
                </div>
                {data.prob15.by_restaurant.length > 0 && (
                  <table className="themed" style={{ marginTop: 12 }}>
                    <thead>
                      <tr>
                        <th>Nhà hàng</th>
                        <th>Đạt/Tổng</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.prob15.by_restaurant.map((r) => (
                        <tr key={r.restaurant_id}>
                          <td>{r.restaurant_name}</td>
                          <td>
                            {r.num}/{r.den}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="card">
                <h3 style={{ marginTop: 0 }}>Phân bổ nhân sự theo thương hiệu</h3>
                {data.by_brand.length === 0 && <p className="muted-note">Chưa có dữ liệu.</p>}
                {data.by_brand.map((b) => {
                  const max = data.by_brand[0].count || 1
                  return (
                    <div key={b.brand} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                        <span>{b.brand}</span>
                        <span>{b.count}</span>
                      </div>
                      <ProgressBar percent={(b.count / max) * 100} />
                    </div>
                  )
                })}
              </div>
            </div>

            <div>
              <div className="card" style={{ marginBottom: 16 }}>
                <h3 style={{ marginTop: 0 }}>Trainer xuất sắc</h3>
                {data.top_trainer ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 28 }}>🏆</span>
                    <div>
                      <div style={{ fontWeight: 600 }}>{data.top_trainer.name}</div>
                      <div className="stat-num amber" style={{ fontSize: '1.2rem' }}>
                        {data.top_trainer.trained} NV đạt
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="muted-note">Chưa có dữ liệu.</p>
                )}
              </div>

              <div style={{ marginBottom: 16 }}>
                <MiniCalendar />
              </div>

              <div className="card">
                <h3 style={{ marginTop: 0 }}>Sắp đến hạn thử việc</h3>
                {data.deadlines.length === 0 && <p className="muted-note">Không có trường hợp nào.</p>}
                {data.deadlines.map((d) => (
                  <div
                    key={d.employee_id}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '6px 0', borderBottom: '1px solid var(--card-border)',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{d.name}</div>
                      <div className="muted-note" style={{ fontSize: 12 }}>
                        {d.restaurant}
                      </div>
                    </div>
                    <Badge variant={d.days_left < 0 ? 'danger' : 'warning'}>
                      {d.days_left < 0 ? `Quá ${-d.days_left} ngày` : `Còn ${d.days_left} ngày`}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </AppShell>
  )
}
