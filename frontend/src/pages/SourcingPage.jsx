import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'

const AUDIENCE = { source: 'Nhân sự nguồn', management: 'Quản lý cấp trung', other: 'Khác' }
const MODE = { offline: 'Offline', online: 'Online' }
const COHORT_STATUS = { open: 'Đang mở đăng ký', ongoing: 'Đang đào tạo', closed: 'Đã kết thúc' }
const COHORT_VARIANT = { open: 'warning', ongoing: 'mint', closed: 'neutral' }
const ENR_STATUS = { registered: 'Đăng ký', studying: 'Đang học', completed: 'Hoàn thành', failed: 'Không đạt' }
const ENR_VARIANT = { registered: 'warning', studying: 'mint', completed: 'success', failed: 'danger' }

function roles(role) {
  const r = (role || '').toLowerCase()
  return { r, manage: ['admin', 'om'].includes(r), enroll: ['admin', 'om', 'bql', 'trainer'].includes(r) }
}

// ---------- Trình soạn nội dung chương trình ----------
function ContentEditor({ program, onClose }) {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState({ session_no: '', topic: '', content: '', doc_url: '' })

  async function load() {
    const { data } = await api.get('/sourcing/program-contents/', { params: { program: program.id } })
    setRows(data)
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [program.id])

  async function add() {
    if (!form.content.trim()) return
    await api.post('/sourcing/program-contents/', {
      program: program.id, ...form,
      session_no: form.session_no === '' ? null : Number(form.session_no),
      order: rows.length + 1,
    })
    setForm({ session_no: '', topic: '', content: '', doc_url: '' })
    load()
  }
  async function del(id) {
    if (!window.confirm('Xoá mục nội dung này?')) return
    await api.delete(`/sourcing/program-contents/${id}/`)
    load()
  }

  return (
    <Modal open title={`Nội dung — ${program.name}`} onClose={onClose} footer={<button className="btn-outline" onClick={onClose}>Đóng</button>}>
      <Table>
        <thead><tr><th>Buổi</th><th>Chủ đề</th><th>Nội dung</th><th></th></tr></thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td>{c.session_no}</td><td>{c.topic}</td>
              <td>{c.content}{c.doc_url && <a href={c.doc_url} target="_blank" rel="noreferrer" style={{ marginLeft: 4 }}>📄</a>}</td>
              <td><button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => del(c.id)}>Xoá</button></td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={4} className="muted-note">Chưa có nội dung.</td></tr>}
        </tbody>
      </Table>
      <div style={{ display: 'grid', gap: 6, gridTemplateColumns: '70px 1fr 1fr', marginTop: 8 }}>
        <input type="number" placeholder="Buổi" value={form.session_no} onChange={(e) => setForm({ ...form, session_no: e.target.value })} />
        <input placeholder="Chủ đề" value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} />
        <input placeholder="Nội dung *" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <input style={{ flex: 1 }} placeholder="Link tài liệu (tuỳ chọn)" value={form.doc_url} onChange={(e) => setForm({ ...form, doc_url: e.target.value })} />
        <button onClick={add}>Thêm mục</button>
      </div>
    </Modal>
  )
}

// ---------- Điểm danh 1 buổi (QR + roster) ----------
function AttendanceModal({ session, canManage, onClose }) {
  const [roster, setRoster] = useState([])
  const url = `${window.location.origin}/attend/${session.qr_token}`

  async function load() {
    const { data } = await api.get(`/sourcing/cohort-sessions/${session.id}/attendance/`)
    setRoster(data.roster)
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [session.id])

  async function toggle(r) {
    await api.post(`/sourcing/cohort-sessions/${session.id}/attendance/`, { enrollment: r.enrollment_id, present: !r.present })
    load()
  }

  return (
    <Modal open title={`Buổi ${session.session_no || ''}${session.title ? ' — ' + session.title : ''}`} onClose={onClose} footer={<button className="btn-outline" onClick={onClose}>Đóng</button>}>
      <div className="card" style={{ padding: 10, textAlign: 'center', marginBottom: 10 }}>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>QR điểm danh</div>
        <img alt="QR điểm danh" width={180} height={180} src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(url)}`} />
        <div style={{ fontSize: 12, wordBreak: 'break-all', marginTop: 6 }}>{url}</div>
        <button className="btn-outline btn-sm" style={{ marginTop: 6 }} onClick={() => navigator.clipboard?.writeText(url)}>Sao chép link</button>
      </div>
      <Table>
        <thead><tr><th>Học viên</th><th>Trạng thái</th>{canManage && <th></th>}</tr></thead>
        <tbody>
          {roster.map((r) => (
            <tr key={r.enrollment_id}>
              <td>{r.employee_name} - {r.employee_code}</td>
              <td>{r.present ? <span style={{ color: 'var(--forest)' }}>✅ Có mặt {r.method === 'self' ? '(tự quét)' : ''}</span> : '—'}</td>
              {canManage && <td><button className="btn-outline btn-sm" onClick={() => toggle(r)}>{r.present ? 'Bỏ' : 'Có mặt'}</button></td>}
            </tr>
          ))}
          {roster.length === 0 && <tr><td colSpan={3} className="muted-note">Chưa có học viên trong đợt.</td></tr>}
        </tbody>
      </Table>
    </Modal>
  )
}

// ---------- Nội dung + kết quả 1 học viên ----------
function EnrollmentModal({ enrollment, canResult, onClose, onChanged }) {
  const [data, setData] = useState(null)

  async function load() {
    const { data } = await api.get(`/sourcing/enrollments/${enrollment.id}/contents/`)
    setData(data)
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [enrollment.id])

  async function toggle(c) {
    await api.post(`/sourcing/enrollments/${enrollment.id}/contents/`, { content: c.content_id, done: !c.done })
    load()
  }
  async function setResult(result) {
    if (!window.confirm(`Chốt kết quả "${result}" cho học viên này?`)) return
    await api.post(`/sourcing/enrollments/${enrollment.id}/result/`, { result })
    onChanged?.()
    onClose()
  }

  const s = data?.summary
  return (
    <Modal open title={`${enrollment.employee_name} — nội dung & kết quả`} onClose={onClose} footer={<button className="btn-outline" onClick={onClose}>Đóng</button>}>
      {!data && <p className="muted-note">Đang tải...</p>}
      {data && (
        <>
          <div className="muted-note" style={{ marginBottom: 8 }}>
            Điểm danh {s.attended}/{s.session_total} buổi ({s.attendance_percent}%) · Nội dung {s.content_done}/{s.content_total} ({s.content_percent}%)
          </div>
          <Table>
            <thead><tr><th>Buổi</th><th>Nội dung</th><th></th></tr></thead>
            <tbody>
              {data.contents.map((c) => (
                <tr key={c.content_id}>
                  <td>{c.session_no}</td>
                  <td>{c.content}{c.doc_url && <a href={c.doc_url} target="_blank" rel="noreferrer" style={{ marginLeft: 4 }}>📄</a>}</td>
                  <td><button className={`btn-sm ${c.done ? '' : 'btn-outline'}`} onClick={() => toggle(c)}>{c.done ? '✅ Xong' : 'Đánh dấu'}</button></td>
                </tr>
              ))}
              {data.contents.length === 0 && <tr><td colSpan={3} className="muted-note">Chương trình chưa có checklist nội dung.</td></tr>}
            </tbody>
          </Table>
          {canResult && (
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button onClick={() => setResult('Đạt')}>Chốt: Đạt</button>
              <button className="btn-outline" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => setResult('Không đạt')}>Chốt: Không đạt</button>
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

// ---------- Chi tiết đợt: buổi học + học viên ----------
function CohortDetailModal({ cohort, canManage, canEnroll, onClose, onChanged }) {
  const [sessions, setSessions] = useState([])
  const [enrollments, setEnrollments] = useState([])
  const [sessForm, setSessForm] = useState(null)
  const [attendSession, setAttendSession] = useState(null)
  const [enrollModal, setEnrollModal] = useState(null)
  const [empTerm, setEmpTerm] = useState('')
  const [empResults, setEmpResults] = useState([])
  const [showInvite, setShowInvite] = useState(false)
  const [showReport, setShowReport] = useState(false)
  const [showEventQR, setShowEventQR] = useState(false)
  const eventUrl = cohort.qr_token ? `${window.location.origin}/event/${cohort.qr_token}` : ''

  async function load() {
    const [ss, en] = await Promise.all([
      api.get('/sourcing/cohort-sessions/', { params: { cohort: cohort.id } }),
      api.get('/sourcing/enrollments/', { params: { cohort: cohort.id } }),
    ])
    setSessions(ss.data)
    setEnrollments(en.data)
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [cohort.id])

  async function addSession() {
    await api.post('/sourcing/cohort-sessions/', {
      cohort: cohort.id,
      session_no: sessForm.session_no === '' ? null : Number(sessForm.session_no),
      title: sessForm.title, date: sessForm.date || null, location: sessForm.location,
    })
    setSessForm(null)
    load()
  }
  async function searchEmp() {
    const { data } = await api.get('/employees/', { params: { search: empTerm, page_size: 8 } })
    setEmpResults(data.results || [])
  }
  async function addEnroll(emp) {
    try {
      await api.post('/sourcing/enrollments/', { cohort: cohort.id, employee: emp.id })
      setEmpTerm(''); setEmpResults([])
      load()
    } catch (e) {
      alert(e.response?.data?.detail || 'Không thêm được học viên.')
    }
  }
  async function removeEnroll(id) {
    if (!window.confirm('Xoá học viên khỏi đợt?')) return
    await api.delete(`/sourcing/enrollments/${id}/`)
    load()
  }

  return (
    <Modal open title={`Đợt: ${cohort.name}`} onClose={onClose} footer={<button className="btn-outline" onClick={onClose}>Đóng</button>}>
      <div className="muted-note" style={{ marginBottom: 8 }}>{cohort.program_name} · <Badge variant={COHORT_VARIANT[cohort.status]}>{COHORT_STATUS[cohort.status]}</Badge></div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        <button className="btn-outline btn-sm" onClick={() => setShowEventQR(true)}>QR sự kiện</button>
        {canEnroll && <button className="btn-outline btn-sm" onClick={() => setShowInvite(true)}>Mời hàng loạt</button>}
        <button className="btn-outline btn-sm" onClick={() => setShowReport(true)}>Báo cáo tham gia</button>
      </div>
      {showEventQR && (
        <div className="card" style={{ padding: 10, textAlign: 'center', marginBottom: 10 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>QR sự kiện — học viên chọn chủ đề rồi điểm danh</div>
          {cohort.qr_token ? (
            <>
              <img alt="QR sự kiện" width={180} height={180} src={'https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=' + encodeURIComponent(eventUrl)} />
              <div style={{ fontSize: 12, wordBreak: 'break-all', marginTop: 6 }}>{eventUrl}</div>
            </>
          ) : <div className="muted-note">Đợt tạo trước bản cập nhật chưa có mã QR sự kiện — tạo đợt mới để có QR.</div>}
          <div><button className="btn-outline btn-sm" style={{ marginTop: 6 }} onClick={() => setShowEventQR(false)}>Đóng</button></div>
        </div>
      )}

      {/* Buổi học */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: '4px 0' }}>Buổi học</h4>
        {canManage && <button className="btn-sm" onClick={() => setSessForm({ session_no: sessions.length + 1, title: '', date: '', location: cohort.location || '' })}>+ Buổi</button>}
      </div>
      <Table>
        <thead><tr><th>Buổi</th><th>Tiêu đề</th><th>Ngày</th><th>Có mặt</th><th></th></tr></thead>
        <tbody>
          {sessions.map((se) => (
            <tr key={se.id}>
              <td>{se.session_no}</td><td>{se.title}</td><td>{se.date}</td><td>{se.attendance_count}</td>
              <td><button className="btn-outline btn-sm" onClick={() => setAttendSession(se)}>QR / Điểm danh</button></td>
            </tr>
          ))}
          {sessions.length === 0 && <tr><td colSpan={5} className="muted-note">Chưa có buổi học.</td></tr>}
        </tbody>
      </Table>

      {/* Học viên */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
        <h4 style={{ margin: '4px 0' }}>Học viên</h4>
      </div>
      {canEnroll && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          <input style={{ flex: 1 }} placeholder="Tìm nhân sự để thêm..." value={empTerm} onChange={(e) => setEmpTerm(e.target.value)} />
          <button className="btn-outline" onClick={searchEmp}>Tìm</button>
        </div>
      )}
      {empResults.length > 0 && (
        <div className="card" style={{ padding: 6, marginBottom: 8, maxHeight: 150, overflow: 'auto' }}>
          {empResults.map((e) => (
            <div key={e.id} style={{ padding: '4px 6px', cursor: 'pointer' }} onClick={() => addEnroll(e)}>
              {e.name} - {e.code} <span className="muted-note">({e.position || '—'})</span>
            </div>
          ))}
        </div>
      )}
      <Table>
        <thead><tr><th>Học viên</th><th>Nhà hàng</th><th>Trạng thái</th><th>Kết quả</th><th></th></tr></thead>
        <tbody>
          {enrollments.map((en) => (
            <tr key={en.id}>
              <td>{en.employee_name} - {en.employee_code}</td>
              <td>{en.restaurant_name}</td>
              <td><Badge variant={ENR_VARIANT[en.status]}>{ENR_STATUS[en.status]}</Badge></td>
              <td>{en.result}</td>
              <td style={{ display: 'flex', gap: 6 }}>
                <button className="btn-outline btn-sm" onClick={() => setEnrollModal(en)}>Nội dung</button>
                {canEnroll && <button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => removeEnroll(en.id)}>Xoá</button>}
              </td>
            </tr>
          ))}
          {enrollments.length === 0 && <tr><td colSpan={5} className="muted-note">Chưa có học viên.</td></tr>}
        </tbody>
      </Table>

      {sessForm && (
        <Modal open title="Thêm buổi học" onClose={() => setSessForm(null)} footer={<><button className="btn-outline" onClick={() => setSessForm(null)}>Hủy</button><button onClick={addSession}>Lưu</button></>}>
          <div style={{ display: 'grid', gap: 8 }}>
            <label>Buổi<input type="number" style={{ display: 'block', width: '100%' }} value={sessForm.session_no} onChange={(e) => setSessForm({ ...sessForm, session_no: e.target.value })} /></label>
            <label>Tiêu đề<input style={{ display: 'block', width: '100%' }} value={sessForm.title} onChange={(e) => setSessForm({ ...sessForm, title: e.target.value })} /></label>
            <label>Ngày<input type="date" style={{ display: 'block', width: '100%' }} value={sessForm.date} onChange={(e) => setSessForm({ ...sessForm, date: e.target.value })} /></label>
            <label>Địa điểm<input style={{ display: 'block', width: '100%' }} value={sessForm.location} onChange={(e) => setSessForm({ ...sessForm, location: e.target.value })} /></label>
          </div>
        </Modal>
      )}
      {attendSession && <AttendanceModal session={attendSession} canManage={canEnroll} onClose={() => { setAttendSession(null); load() }} />}
      {enrollModal && <EnrollmentModal enrollment={enrollModal} canResult={canEnroll} onClose={() => setEnrollModal(null)} onChanged={() => { load(); onChanged?.() }} />}
      {showInvite && <InviteModal cohort={cohort} onClose={() => setShowInvite(false)} onDone={() => { setShowInvite(false); load() }} />}
      {showReport && <ReportModal cohort={cohort} onClose={() => setShowReport(false)} />}
    </Modal>
  )
}

// ---------- Mời hàng loạt theo bộ lọc ----------
function InviteModal({ cohort, onClose, onDone }) {
  const [f, setF] = useState({ level_group: '', operation_unit: '', position: '' })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  async function submit() {
    setBusy(true); setMsg('')
    try {
      const { data } = await api.post(`/sourcing/cohorts/${cohort.id}/bulk-enroll/`, {
        level_group: f.level_group || undefined,
        operation_unit: f.operation_unit || undefined,
        position: f.position || undefined,
      })
      setMsg(`Đã mời ${data.invited} người (đã có sẵn ${data.already_in}, gửi thông báo ${data.notified_users} tài khoản).`)
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Mời thất bại.')
    } finally { setBusy(false) }
  }

  return (
    <Modal open title="Mời hàng loạt theo bộ lọc" onClose={onClose}
      footer={<><button className="btn-outline" onClick={onClose}>Đóng</button><button disabled={busy} onClick={submit}>Lọc & mời</button></>}>
      <div style={{ display: 'grid', gap: 10 }}>
        <label>Nhóm level
          <select style={{ display: 'block', width: '100%' }} value={f.level_group} onChange={(e) => setF({ ...f, level_group: e.target.value })}>
            <option value="">Tất cả</option><option value="S">S</option><option value="O">O</option><option value="P">P (part-time)</option>
          </select>
        </label>
        <label>Khối
          <select style={{ display: 'block', width: '100%' }} value={f.operation_unit} onChange={(e) => setF({ ...f, operation_unit: e.target.value })}>
            <option value="">Tất cả</option><option value="restaurant">Nhà hàng</option><option value="office">Văn phòng</option><option value="production">Sản xuất</option>
          </select>
        </label>
        <label>Vị trí chứa
          <input style={{ display: 'block', width: '100%' }} value={f.position} onChange={(e) => setF({ ...f, position: e.target.value })} placeholder="vd: Bếp trưởng, Giám sát..." />
        </label>
        <p className="muted-note" style={{ fontSize: 12 }}>Loại nhân sự đã nghỉ. Thông báo gửi tới tài khoản có tên khớp nhân sự được mời + phòng đào tạo.</p>
        {msg && <p style={{ color: 'var(--forest-dark)' }}>{msg}</p>}
      </div>
    </Modal>
  )
}

// ---------- Báo cáo tham gia ----------
function ReportModal({ cohort, onClose }) {
  const [data, setData] = useState(null)
  useEffect(() => { api.get(`/sourcing/cohorts/${cohort.id}/report/`).then(({ data }) => setData(data)) }, [cohort.id])

  function exportCsv() {
    const cell = (c) => '"' + String(c == null ? '' : c).split('"').join('""') + '"'
    const head = ['Mã', 'Họ tên', 'Nhà hàng', 'Có mặt', 'Tổng buổi', '%', 'Kết quả']
    const lines = data.people.map((p) => [p.employee_code, p.employee_name, p.restaurant_name, p.attended, p.total_sessions, p.percent, p.result])
    const csv = [head, ...lines].map((r) => r.map(cell).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = 'bao_cao_' + cohort.name + '.csv'; a.click()
  }

  return (
    <Modal open title={`Báo cáo tham gia — ${cohort.name}`} onClose={onClose}
      footer={<><button className="btn-outline" onClick={onClose}>Đóng</button>{data && <button onClick={exportCsv}>Tải CSV</button>}</>}>
      {!data && <p className="muted-note">Đang tải...</p>}
      {data && (
        <>
          <div style={{ fontWeight: 700, margin: '4px 0' }}>Theo buổi (mời {data.invited_total})</div>
          <Table>
            <thead><tr><th>Buổi</th><th>Chủ đề</th><th>Ngày</th><th>Có mặt / Mời</th></tr></thead>
            <tbody>
              {data.sessions.map((s) => (
                <tr key={s.session_id}><td>{s.session_no}</td><td>{s.title}</td><td>{s.date}</td><td>{s.present}/{s.invited}</td></tr>
              ))}
              {data.sessions.length === 0 && <tr><td colSpan={4} className="muted-note">Chưa có buổi.</td></tr>}
            </tbody>
          </Table>
          <div style={{ fontWeight: 700, margin: '10px 0 4px' }}>Theo học viên</div>
          <Table>
            <thead><tr><th>Học viên</th><th>Nhà hàng</th><th>Tham gia</th><th>%</th></tr></thead>
            <tbody>
              {data.people.map((p) => (
                <tr key={p.employee_code}><td>{p.employee_name} - {p.employee_code}</td><td>{p.restaurant_name}</td><td>{p.attended}/{p.total_sessions}</td><td>{p.percent}%</td></tr>
              ))}
              {data.people.length === 0 && <tr><td colSpan={4} className="muted-note">Chưa có học viên.</td></tr>}
            </tbody>
          </Table>
        </>
      )}
    </Modal>
  )
}

export default function SourcingPage() {
  const { user } = useAuth()
  const f = roles(user?.role)
  const [searchParams] = useSearchParams()
  const [audienceF, setAudienceF] = useState(searchParams.get('audience') || '')
  const [tab, setTab] = useState(f.manage ? 'programs' : 'cohorts')
  const [programs, setPrograms] = useState([])
  const [cohorts, setCohorts] = useState([])
  const [progForm, setProgForm] = useState(null)
  const [contentProgram, setContentProgram] = useState(null)
  const [cohortForm, setCohortForm] = useState(null)
  const [openCohort, setOpenCohort] = useState(null)

  async function loadPrograms() {
    const { data } = await api.get('/sourcing/programs/', { params: { page_size: 100 } })
    setPrograms(data.results || [])
  }
  async function loadCohorts() {
    const { data } = await api.get('/sourcing/cohorts/', { params: { page_size: 100 } })
    setCohorts(data.results || [])
  }
  useEffect(() => { loadPrograms(); loadCohorts() }, [])

  async function saveProgram() {
    if (progForm.id) await api.patch(`/sourcing/programs/${progForm.id}/`, progForm)
    else await api.post('/sourcing/programs/', progForm)
    setProgForm(null); loadPrograms()
  }

  const shownPrograms = audienceF ? programs.filter((p) => p.audience === audienceF) : programs
  const shownCohorts = audienceF ? cohorts.filter((c) => c.audience === audienceF) : cohorts
  async function saveCohort() {
    await api.post('/sourcing/cohorts/', {
      ...cohortForm, start_date: cohortForm.start_date || null, end_date: cohortForm.end_date || null,
    })
    setCohortForm(null); loadCohorts()
  }
  async function setCohortStatus(c, status) {
    await api.patch(`/sourcing/cohorts/${c.id}/`, { status })
    loadCohorts()
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Đào tạo nguồn & Quản lý</h2>
      </div>
      <div style={{ display: 'flex', gap: 8, margin: '10px 0', alignItems: 'center', flexWrap: 'wrap' }}>
        {f.manage && <button className={`btn-sm ${tab === 'programs' ? '' : 'btn-outline'}`} onClick={() => setTab('programs')}>Chương trình</button>}
        <button className={`btn-sm ${tab === 'cohorts' ? '' : 'btn-outline'}`} onClick={() => setTab('cohorts')}>Đợt đào tạo</button>
        <span style={{ flex: 1 }} />
        <select value={audienceF} onChange={(e) => setAudienceF(e.target.value)}>
          <option value="">Tất cả đối tượng</option>
          {Object.entries(AUDIENCE).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {tab === 'programs' && f.manage && (
        <>
          <div style={{ marginBottom: 8 }}><button onClick={() => setProgForm({ name: '', audience: audienceF || 'source', mode: 'offline', source_url: '', description: '', is_active: true })}>+ Chương trình</button></div>
          <Table>
            <thead><tr><th>Tên</th><th>Đối tượng</th><th>Hình thức</th><th>Nội dung</th><th>Đợt</th><th></th></tr></thead>
            <tbody>
              {shownPrograms.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td><td>{AUDIENCE[p.audience]}</td>
                  <td>{MODE[p.mode]}{p.mode === 'online' && p.source_url && <a href={p.source_url} target="_blank" rel="noreferrer" style={{ marginLeft: 4 }}>🔗</a>}</td>
                  <td>{p.content_count}</td><td>{p.cohort_count}</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button className="btn-outline btn-sm" onClick={() => setContentProgram(p)}>Nội dung</button>
                    <button className="btn-outline btn-sm" onClick={() => setProgForm(p)}>Sửa</button>
                  </td>
                </tr>
              ))}
              {shownPrograms.length === 0 && <tr><td colSpan={6} className="muted-note">Chưa có chương trình.</td></tr>}
            </tbody>
          </Table>
        </>
      )}

      {tab === 'cohorts' && (
        <>
          {f.manage && <div style={{ marginBottom: 8 }}><button disabled={shownPrograms.length === 0} onClick={() => setCohortForm({ program: shownPrograms[0]?.id, name: '', location: '', start_date: '', end_date: '' })}>+ Đợt đào tạo</button></div>}
          <Table>
            <thead><tr><th>Đợt</th><th>Chương trình</th><th>Buổi</th><th>Học viên</th><th>Trạng thái</th><th></th></tr></thead>
            <tbody>
              {shownCohorts.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td><td>{c.program_name}</td><td>{c.session_count}</td><td>{c.enrollment_count}</td>
                  <td>
                    {f.manage ? (
                      <select value={c.status} onChange={(e) => setCohortStatus(c, e.target.value)}>
                        {Object.entries(COHORT_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    ) : <Badge variant={COHORT_VARIANT[c.status]}>{COHORT_STATUS[c.status]}</Badge>}
                  </td>
                  <td><button className="btn-outline btn-sm" onClick={() => setOpenCohort(c)}>Mở</button></td>
                </tr>
              ))}
              {shownCohorts.length === 0 && <tr><td colSpan={6} className="muted-note">Chưa có đợt đào tạo.</td></tr>}
            </tbody>
          </Table>
        </>
      )}

      {progForm && (
        <Modal open title={progForm.id ? 'Sửa chương trình' : 'Thêm chương trình'} onClose={() => setProgForm(null)} footer={<><button className="btn-outline" onClick={() => setProgForm(null)}>Hủy</button><button onClick={saveProgram}>Lưu</button></>}>
          <div style={{ display: 'grid', gap: 10 }}>
            <label>Tên<input style={{ display: 'block', width: '100%' }} value={progForm.name} onChange={(e) => setProgForm({ ...progForm, name: e.target.value })} /></label>
            <label>Đối tượng
              <select style={{ display: 'block', width: '100%' }} value={progForm.audience} onChange={(e) => setProgForm({ ...progForm, audience: e.target.value })}>
                {Object.entries(AUDIENCE).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label>Hình thức
              <select style={{ display: 'block', width: '100%' }} value={progForm.mode || 'offline'} onChange={(e) => setProgForm({ ...progForm, mode: e.target.value })}>
                <option value="offline">Offline (điểm danh trực tiếp)</option>
                <option value="online">Online (học/thi trên nền tảng)</option>
              </select>
            </label>
            {progForm.mode === 'online' && (
              <label>Link nguồn học/thi (online)
                <input style={{ display: 'block', width: '100%' }} value={progForm.source_url || ''} onChange={(e) => setProgForm({ ...progForm, source_url: e.target.value })} placeholder="https://..." />
              </label>
            )}
            <label>Mô tả<textarea style={{ display: 'block', width: '100%' }} rows={3} value={progForm.description} onChange={(e) => setProgForm({ ...progForm, description: e.target.value })} /></label>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={progForm.is_active} onChange={(e) => setProgForm({ ...progForm, is_active: e.target.checked })} /> Đang áp dụng</label>
          </div>
        </Modal>
      )}
      {cohortForm && (
        <Modal open title="Thêm đợt đào tạo" onClose={() => setCohortForm(null)} footer={<><button className="btn-outline" onClick={() => setCohortForm(null)}>Hủy</button><button onClick={saveCohort}>Lưu</button></>}>
          <div style={{ display: 'grid', gap: 10 }}>
            <label>Chương trình
              <select style={{ display: 'block', width: '100%' }} value={cohortForm.program} onChange={(e) => setCohortForm({ ...cohortForm, program: e.target.value })}>
                {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label>Tên đợt<input style={{ display: 'block', width: '100%' }} value={cohortForm.name} onChange={(e) => setCohortForm({ ...cohortForm, name: e.target.value })} /></label>
            <label>Địa điểm<input style={{ display: 'block', width: '100%' }} value={cohortForm.location} onChange={(e) => setCohortForm({ ...cohortForm, location: e.target.value })} /></label>
            <div style={{ display: 'flex', gap: 8 }}>
              <label style={{ flex: 1 }}>Bắt đầu<input type="date" style={{ display: 'block', width: '100%' }} value={cohortForm.start_date} onChange={(e) => setCohortForm({ ...cohortForm, start_date: e.target.value })} /></label>
              <label style={{ flex: 1 }}>Kết thúc<input type="date" style={{ display: 'block', width: '100%' }} value={cohortForm.end_date} onChange={(e) => setCohortForm({ ...cohortForm, end_date: e.target.value })} /></label>
            </div>
          </div>
        </Modal>
      )}
      {contentProgram && <ContentEditor program={contentProgram} onClose={() => { setContentProgram(null); loadPrograms() }} />}
      {openCohort && <CohortDetailModal cohort={openCohort} canManage={f.manage} canEnroll={f.enroll} onClose={() => { setOpenCohort(null); loadCohorts() }} onChanged={loadCohorts} />}
    </AppShell>
  )
}
