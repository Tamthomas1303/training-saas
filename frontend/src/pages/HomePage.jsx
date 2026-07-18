import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import ProgressBar from '../components/ProgressBar'
import StatCard from '../components/StatCard'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'

const STATUS_VARIANTS = { not_started: 'neutral', in_progress: 'mint', done: 'success' }
const STATUS_LABELS = { not_started: 'Chưa bắt đầu', in_progress: 'Đang thực hiện', done: 'Hoàn thành' }

function fmtMoney(n) {
  return `${Math.round(n || 0).toLocaleString('vi-VN')}đ`
}

function deadlineText(days) {
  if (days == null) return null
  return days < 0 ? `Quá ${-days} ngày` : `Còn ${days} ngày`
}

export default function HomePage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/employees/home/')
      .then(({ data }) => setData(data))
      .catch(() => setError('Không tải được số liệu.'))
  }, [])

  const role = (user.role || '').toLowerCase()
  const canCoach = role === 'am' || role === 'kcs'

  return (
    <AppShell>
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, var(--forest), var(--green))',
          color: '#fff', border: 'none', marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 12,
        }}
      >
        <div
          style={{
            width: 48, height: 48, borderRadius: '50%', background: 'rgba(255,255,255,.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {(user.full_name || user.username || '?').charAt(0).toUpperCase()}
        </div>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ color: '#fff', margin: 0, overflowWrap: 'anywhere' }}>
            Xin chào, {user.full_name || user.username}
          </h2>
          <p style={{ margin: '4px 0 0', opacity: 0.9 }}>Vai trò: {user.role}</p>
        </div>
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!error && !data && <p className="muted-note">Đang tải...</p>}

      {data && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
            <StatCard label="Cần đào tạo" value={data.summary.need} />
            <StatCard label="Đạt thử việc" value={data.summary.passed} />
            <StatCard label="Đủ ĐK hoa hồng" amber value={data.summary.commission_eligible}>
              <div className="muted-note" style={{ marginTop: 4 }}>
                ~{fmtMoney(data.summary.commission_amount)}
              </div>
            </StatCard>
          </div>

          {canCoach && (
            <div style={{ marginBottom: 16 }}>
              <Link to="/kpi">
                <button>Tổ chức buổi đào tạo (coaching)</button>
              </Link>
            </div>
          )}

          <h3>Tiến độ đào tạo từng nhân sự</h3>
          {data.rows.length === 0 && <p className="muted-note">Chưa có nhân sự phụ trách.</p>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
            {data.rows.map((r) => (
              <div key={r.employee_id} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div style={{ fontWeight: 600 }}>
                    {r.name} - {r.code}
                  </div>
                  <Badge variant={STATUS_VARIANTS[r.status]}>{STATUS_LABELS[r.status]}</Badge>
                </div>
                <div className="muted-note" style={{ fontSize: 12, margin: '4px 0 8px' }}>
                  {r.position} · {r.restaurant}
                </div>
                <ProgressBar percent={r.progress} />
                <div className="muted-note" style={{ fontSize: 12, marginTop: 8 }}>
                  {r.progress}%{deadlineText(r.days_left) ? ` · ${deadlineText(r.days_left)}` : ''}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  <button
                    className="btn-sm"
                    onClick={() =>
                      navigate('/training', {
                        state: {
                          employee: {
                            id: r.employee_id, name: r.name,
                            position: r.position, restaurant_name: r.restaurant,
                          },
                        },
                      })
                    }
                  >
                    Bắt đầu đào tạo
                  </button>
                  <Link to={`/employees/${r.employee_id}`}>
                    <button className="btn-outline btn-sm">Chi tiết</button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </AppShell>
  )
}
