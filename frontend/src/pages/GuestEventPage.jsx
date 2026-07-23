import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client'

// QR cấp sự kiện: học viên chọn CHỦ ĐỀ (buổi) → chọn tên → điểm danh. Không cần đăng nhập.
export default function GuestEventPage() {
  const { token } = useParams()
  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [term, setTerm] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [done, setDone] = useState('')

  useEffect(() => {
    api.get(`/sourcing/event/${token}/`).then(({ data }) => {
      setInfo(data)
      if (data.sessions?.length === 1) setSessionId(String(data.sessions[0].id))
    }).catch(() => setError('Link không hợp lệ hoặc đã hết hạn.'))
  }, [token])

  async function checkIn(r) {
    if (!sessionId) { setError('Hãy chọn chủ đề trước.'); return }
    setBusyId(r.enrollment_id); setError('')
    try {
      const { data } = await api.post(`/sourcing/event/${token}/checkin/`, { session: sessionId, enrollment: r.enrollment_id })
      setDone(`${data.name} — đã điểm danh chủ đề "${data.session}".`)
    } catch (e) {
      setError(e.response?.data?.detail || 'Điểm danh thất bại.')
    } finally { setBusyId(null) }
  }

  const roster = (info?.roster || []).filter(
    (r) => !term || r.employee_name.toLowerCase().includes(term.toLowerCase()) || (r.employee_code || '').toLowerCase().includes(term.toLowerCase())
  )

  return (
    <div className="login-page" style={{ alignItems: 'flex-start', minHeight: '100vh' }}>
      <div className="login-card" style={{ maxWidth: 520, width: '100%', margin: '24px auto' }}>
        {!info && !error && <p>Đang tải...</p>}
        {error && !info && <p style={{ color: 'var(--danger)' }}>{error}</p>}
        {info && (
          <>
            <h2 style={{ marginTop: 0 }}>Điểm danh đào tạo</h2>
            <p className="muted-note">{info.program} · {info.cohort}</p>

            <label style={{ display: 'block', marginBottom: 10 }}>
              Chủ đề tham gia
              <select style={{ display: 'block', width: '100%' }} value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
                <option value="">— Chọn chủ đề/buổi —</option>
                {info.sessions.map((s) => (
                  <option key={s.id} value={s.id}>{s.title}{s.date ? ` · ${s.date}` : ''}</option>
                ))}
              </select>
            </label>

            {done && <p style={{ color: 'var(--forest)', fontWeight: 600 }}>✅ {done} Có thể đóng trang.</p>}

            <input style={{ width: '100%', marginBottom: 10 }} placeholder="Tìm tên / mã của bạn..." value={term} onChange={(e) => setTerm(e.target.value)} />
            <div style={{ display: 'grid', gap: 6 }}>
              {roster.map((r) => (
                <div key={r.enrollment_id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 10 }}>
                  <div><div style={{ fontWeight: 600 }}>{r.employee_name}</div><div className="muted-note" style={{ fontSize: 12 }}>{r.employee_code}</div></div>
                  <button disabled={busyId === r.enrollment_id || !sessionId} onClick={() => checkIn(r)}>{busyId === r.enrollment_id ? '...' : 'Tôi có mặt'}</button>
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
