import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client'

// Trang học viên QUÉT QR mở ra — tự điểm danh, không cần đăng nhập.
export default function GuestAttendPage() {
  const { token } = useParams()
  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const [term, setTerm] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [doneName, setDoneName] = useState('')

  async function load() {
    try {
      const { data } = await api.get(`/sourcing/attend/${token}/`)
      setInfo(data)
    } catch {
      setError('Link điểm danh không hợp lệ hoặc đã hết hạn.')
    }
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [token])

  async function checkIn(r) {
    setBusyId(r.enrollment_id)
    setError('')
    try {
      const { data } = await api.post(`/sourcing/attend/${token}/checkin/`, { enrollment: r.enrollment_id })
      setDoneName(data.name)
      await load()
    } catch (e) {
      setError(e.response?.data?.detail || 'Điểm danh thất bại.')
    } finally {
      setBusyId(null)
    }
  }

  const roster = (info?.roster || []).filter(
    (r) => !term ||
      r.employee_name.toLowerCase().includes(term.toLowerCase()) ||
      (r.employee_code || '').toLowerCase().includes(term.toLowerCase())
  )

  return (
    <div className="login-page" style={{ alignItems: 'flex-start', minHeight: '100vh' }}>
      <div className="login-card" style={{ maxWidth: 520, width: '100%', margin: '24px auto' }}>
        {!info && !error && <p>Đang tải...</p>}
        {error && !info && <p style={{ color: 'var(--danger)' }}>{error}</p>}
        {info && (
          <>
            <h2 style={{ marginTop: 0 }}>Điểm danh</h2>
            <p className="muted-note">
              {info.program} · {info.cohort}
              <br />
              Buổi {info.session.session_no}{info.session.title ? ` — ${info.session.title}` : ''}
              {info.session.date ? ` · ${info.session.date}` : ''}
              {info.session.location ? ` · ${info.session.location}` : ''}
            </p>

            {doneName && (
              <p style={{ color: 'var(--forest)', fontWeight: 600 }}>
                ✅ Đã điểm danh cho {doneName}. Bạn có thể đóng trang này.
              </p>
            )}

            <input
              style={{ width: '100%', marginBottom: 10 }}
              placeholder="Tìm tên / mã của bạn..."
              value={term}
              onChange={(e) => setTerm(e.target.value)}
            />
            <div style={{ display: 'grid', gap: 6 }}>
              {roster.map((r) => (
                <div
                  key={r.enrollment_id}
                  className="card"
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 10 }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{r.employee_name}</div>
                    <div className="muted-note" style={{ fontSize: 12 }}>{r.employee_code}{r.restaurant_name ? ` · ${r.restaurant_name}` : ''}</div>
                  </div>
                  {r.present ? (
                    <span style={{ color: 'var(--forest)', fontWeight: 600 }}>Đã điểm danh</span>
                  ) : (
                    <button disabled={busyId === r.enrollment_id} onClick={() => checkIn(r)}>
                      {busyId === r.enrollment_id ? '...' : 'Tôi có mặt'}
                    </button>
                  )}
                </div>
              ))}
              {roster.length === 0 && <p className="muted-note">Không tìm thấy học viên.</p>}
            </div>
            {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
          </>
        )}
      </div>
    </div>
  )
}
