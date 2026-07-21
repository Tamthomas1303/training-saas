import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import ScoreForm from './ScoreForm'

const DEPT_ROLES = [
  { value: 'HCNS', label: 'TP HCNS (Chủ tịch)' },
  { value: 'DaoTao', label: 'TP Đào tạo (Phó chủ tịch)' },
  { value: 'VanHanh', label: 'TP Vận hành (Ủy viên)' },
  { value: 'QC', label: 'TP QC (Ủy viên)' },
]

function fullGuestLink(path) {
  return `${window.location.origin}${path}`
}

// ---- Một hội đồng (tay nghề hoặc phỏng vấn) ----
function CouncilSection({ employee, kind, title, isAdmin, userId }) {
  const [detail, setDetail] = useState(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [users, setUsers] = useState([])
  const [pickUser, setPickUser] = useState('')
  const [deptRole, setDeptRole] = useState(kind === 'interview' ? 'HCNS' : '')
  const [guestName, setGuestName] = useState('')
  const [guestDept, setGuestDept] = useState('')
  const [scoringMember, setScoringMember] = useState(null) // member-form đang chấm
  const [busy, setBusy] = useState(false)

  function load() {
    api.get('/evaluation/council-o/', { params: { employee: employee.id, kind } }).then(({ data }) => setDetail(data))
  }
  useEffect(load, [employee.id, kind])
  useEffect(() => {
    if (isAdmin) api.get('/auth/users/', { params: { page_size: 100 } }).then(({ data }) => setUsers(data.results || []))
  }, [isAdmin])

  async function createCouncil() {
    setErr('')
    try {
      const { data } = await api.post('/evaluation/council-o/create/', { employee: employee.id, kind })
      setDetail({ ...data, exists: true })
    } catch (e) {
      setErr(e.response?.data?.detail || 'Không lập được hội đồng.')
    }
  }

  async function addUserMember() {
    if (!pickUser) return
    setErr('')
    try {
      const { data } = await api.post('/evaluation/council-o/add-member/', {
        council: detail.council_id, user_id: pickUser, dept_role: deptRole,
      })
      setDetail({ ...data, exists: true })
      setPickUser('')
    } catch (e) {
      setErr(e.response?.data?.detail || 'Không thêm được thành viên.')
    }
  }

  async function addGuest() {
    if (!guestName) return
    setErr('')
    try {
      const { data } = await api.post('/evaluation/council-o/add-member/', {
        council: detail.council_id, guest_name: guestName, guest_dept: guestDept, dept_role: deptRole,
      })
      setDetail({ ...data, exists: true })
      setGuestName('')
      setGuestDept('')
    } catch (e) {
      setErr(e.response?.data?.detail || 'Không thêm được khách mời.')
    }
  }

  async function openScoring(memberId) {
    setErr('')
    const { data } = await api.get('/evaluation/council-o/member-form/', { params: { member: memberId } })
    setScoringMember({ id: memberId, ...data })
  }

  async function submitScore(scores, dish, sign) {
    setBusy(true)
    setErr('')
    try {
      await api.post('/evaluation/council-o/submit/', {
        member: scoringMember.id, scores, dish_name: dish, sign,
      })
      setMsg('Đã gửi điểm.')
      setScoringMember(null)
      load()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Gửi điểm thất bại.')
    } finally {
      setBusy(false)
    }
  }

  async function finalize() {
    setErr('')
    try {
      const { data } = await api.post('/evaluation/council-o/finalize/', { council: detail.council_id })
      setMsg(`Đã chốt: ${data.overall}% — ${data.passed ? 'Đạt' : 'Chưa đạt'}.`)
      load()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Chốt hội đồng thất bại.')
    }
  }

  async function exportPdf() {
    setErr('')
    try {
      const { data } = await api.get('/evaluation/council-o/pdf/', { params: { council: detail.council_id } })
      if (data.pdf_url) window.open(data.pdf_url, '_blank')
    } catch (e) {
      setErr(e.response?.data?.detail || 'Xuất PDF thất bại.')
    }
  }

  if (!detail) return <p className="muted-note">Đang tải {title}...</p>

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h4 style={{ marginTop: 0 }}>{title}</h4>

      {!detail.exists ? (
        isAdmin ? (
          <button onClick={createCouncil}>Lập hội đồng</button>
        ) : (
          <p className="muted-note">Chưa được lập. Chờ Admin/Phòng Đào tạo lập hội đồng.</p>
        )
      ) : (
        <>
          <div style={{ marginBottom: 8 }}>
            Tổng hợp: <b>{detail.overall}%</b> ({detail.submitted_count} người chấm) ·{' '}
            <span style={{ color: detail.passed ? 'var(--forest)' : 'var(--danger)' }}>
              {detail.passed ? 'Đạt' : 'Chưa đạt'}
            </span>{' '}
            · {detail.status === 'finalized' ? 'Đã chốt' : 'Đang mở'}
            {' '}
            <button className="btn-outline btn-sm" style={{ marginLeft: 8 }} onClick={exportPdf}>Xuất PDF</button>
          </div>

          <table className="themed" style={{ marginBottom: 8 }}>
            <thead>
              <tr>
                <th>Thành viên</th>
                <th>Vai</th>
                <th>Kết quả</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {detail.members.map((m) => (
                <tr key={m.member_id}>
                  <td>
                    {m.name} {m.is_guest && <span className="muted-note">(khách mời)</span>}
                  </td>
                  <td>{m.dept_role || '—'}</td>
                  <td>{m.submitted ? `${m.result_percent}%` : 'Chưa chấm'}</td>
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {!m.is_guest && m.user_id === userId && (
                      <button className="btn-sm" onClick={() => openScoring(m.member_id)}>Chấm điểm</button>
                    )}
                    {m.is_guest && m.guest_link && (
                      <button
                        className="btn-sm btn-outline"
                        onClick={() => navigator.clipboard?.writeText(fullGuestLink(m.guest_link))}
                        title={fullGuestLink(m.guest_link)}
                      >
                        Sao chép link
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {detail.members.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted-note">Chưa có thành viên.</td>
                </tr>
              )}
            </tbody>
          </table>

          {scoringMember && (
            <div className="card" style={{ marginBottom: 8, background: 'var(--page-bg)' }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Chấm điểm của bạn</div>
              <ScoreForm
                criteria={scoringMember.criteria}
                showDish={kind === 'skill'}
                onSubmit={submitScore}
                busy={busy}
              />
              <button className="btn-outline btn-sm" style={{ marginTop: 8 }} onClick={() => setScoringMember(null)}>
                Đóng
              </button>
            </div>
          )}

          {isAdmin && detail.status !== 'finalized' && (
            <div style={{ borderTop: '1px solid var(--card-border)', paddingTop: 8 }}>
              <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 14 }}>Thêm thành viên</div>
              {kind === 'interview' && (
                <select value={deptRole} onChange={(e) => setDeptRole(e.target.value)} style={{ marginBottom: 6 }}>
                  {DEPT_ROLES.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              )}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                <select value={pickUser} onChange={(e) => setPickUser(e.target.value)}>
                  <option value="">— Chọn tài khoản (OM/AM/KCS…) —</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name || u.username} ({u.role})</option>
                  ))}
                </select>
                <button className="btn-sm" onClick={addUserMember}>Thêm</button>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <input placeholder="Tên khách mời (QC/HCNS…)" value={guestName} onChange={(e) => setGuestName(e.target.value)} style={{ width: 180 }} />
                <input placeholder="Bộ phận" value={guestDept} onChange={(e) => setGuestDept(e.target.value)} style={{ width: 120 }} />
                <button className="btn-sm btn-outline" onClick={addGuest}>Thêm khách mời (link)</button>
              </div>
              <div style={{ marginTop: 10 }}>
                <button onClick={finalize}>Chốt hội đồng</button>
              </div>
            </div>
          )}
        </>
      )}
      {msg && <p style={{ color: 'var(--forest)' }}>{msg}</p>}
      {err && <p style={{ color: 'var(--danger)' }}>{err}</p>}
    </div>
  )
}

// ---- Vận hành ca (AM/KCS) ----
function ShiftOpsSection({ employee, role }) {
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/evaluation/shiftops/', { params: { employee: employee.id } }).then(({ data }) => setForm(data))
  }, [employee.id])

  async function submit(scores, dish, sign) {
    setBusy(true)
    setErr('')
    try {
      const { data } = await api.post('/evaluation/shiftops/save/', { employee: employee.id, scores, sign })
      setMsg(`Đã chấm vận hành ca: ${data.percent}% — ${data.result}.`)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Chấm thất bại.')
    } finally {
      setBusy(false)
    }
  }

  if (!form) return null
  const canScore = ['am', 'kcs', 'admin', 'om'].includes(role)
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h4 style={{ marginTop: 0 }}>Đánh giá vận hành ca ({form.position_group}) — {role === 'kcs' ? 'KCS' : 'AM'}</h4>
      {canScore ? (
        <ScoreForm criteria={form.criteria} onSubmit={submit} busy={busy} submitLabel="Lưu vận hành ca" />
      ) : (
        <p className="muted-note">Chỉ AM (FOH) / KCS (BOH) chấm vận hành ca.</p>
      )}
      {msg && <p style={{ color: 'var(--forest)' }}>{msg}</p>}
      {err && <p style={{ color: 'var(--danger)' }}>{err}</p>}
    </div>
  )
}

export default function CouncilPanel({ employee }) {
  const { user } = useAuth()
  const role = (user?.role || '').toLowerCase()
  const isAdmin = ['admin', 'om'].includes(role)
  const showShiftOps = ['am', 'kcs', 'admin', 'om'].includes(role)
  const [winStatus, setWinStatus] = useState(null)

  useEffect(() => {
    api.get('/evaluation/shiftops/', { params: { employee: employee.id } })
      .then(({ data }) => setWinStatus(data.window))
      .catch(() => {})
  }, [employee.id])

  return (
    <div>
      <h3>Hội đồng đánh giá cấp O — {employee.name}</h3>
      {winStatus && !winStatus.can && (
        <div className="card" style={{ background: '#fff7e6', borderColor: '#f0c36d', marginBottom: 12 }}>
          <b>⏳ {winStatus.reason}</b>
          <div className="muted-note" style={{ fontSize: 12 }}>
            Cửa sổ đánh giá cấp O: từ ngày làm việc thứ 45 đến hết ngày 60.
          </div>
        </div>
      )}
      {winStatus && winStatus.can && (
        <p className="muted-note" style={{ fontSize: 13 }}>
          Trong khung đánh giá (đã làm {winStatus.days}/60 ngày).
        </p>
      )}
      {showShiftOps && <ShiftOpsSection employee={employee} role={role} />}
      <CouncilSection employee={employee} kind="skill" title="Hội đồng tay nghề" isAdmin={isAdmin} userId={user?.id} />
      <CouncilSection employee={employee} kind="interview" title="Hội đồng phỏng vấn" isAdmin={isAdmin} userId={user?.id} />
    </div>
  )
}
