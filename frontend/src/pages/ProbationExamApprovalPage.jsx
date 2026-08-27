import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

// Nhom 3B (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 2/5) - man "Cho duyet thi": danh sach nhan su
// da du dieu kien (LMS xong + checklist 100% + co ProbationExamRule khop vi tri) nhung CHUA
// duoc cho thi - Admin/Trainer duyet (tao/dua vao 1 Ky thi) hoac tu choi (kem ly do).

function ApproveModal({ candidate, open, onClose, onDone }) {
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [supervised, setSupervised] = useState(false)
  const [proctorIds, setProctorIds] = useState([])
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setStartAt(''); setEndAt(''); setSupervised(false); setProctorIds([]); setError('')
    api.get('/auth/users/', { params: { page_size: 200 } }).then(({ data }) => setUsers(data.results ?? data)).catch(() => {})
  }, [open])

  async function submit() {
    setSaving(true)
    setError('')
    try {
      await api.post(`/employees/probation-exam-candidates/${candidate.id}/approve/`, {
        start_at: startAt ? new Date(startAt).toISOString() : null,
        end_at: endAt ? new Date(endAt).toISOString() : null,
        supervised_by_restaurant_camera: supervised,
        proctors: proctorIds,
      })
      onDone()
    } catch (err) {
      setError(err.response?.data?.detail || 'Duyệt thất bại.')
    } finally {
      setSaving(false)
    }
  }

  if (!candidate) return null

  return (
    <Modal open={open} title={`Duyệt thi - ${candidate.employee_name}`} onClose={onClose}>
      <p className="muted-note">
        Tạo kỳ thi riêng cho nhân sự này với đề "{candidate.assessment_title}". Để trống thời gian = mở ngay, không giới hạn đóng.
      </p>
      <div style={{ display: 'flex', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 13 }}>
          Mở lúc{' '}
          <input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} style={s.input} />
        </label>
        <label style={{ fontSize: 13 }}>
          Đóng lúc{' '}
          <input type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} style={s.input} />
        </label>
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <input type="checkbox" checked={supervised} onChange={(e) => setSupervised(e.target.checked)} />
        Giám sát qua camera nhà hàng (bật ghi bằng chứng webcam định kỳ)
      </label>
      {supervised && (
        <label style={{ display: 'block', marginBottom: 8 }}>
          Người coi thi
          <select
            multiple style={{ ...s.select, width: '100%', minHeight: 90 }}
            value={proctorIds}
            onChange={(e) => setProctorIds(Array.from(e.target.selectedOptions, (o) => o.value))}
          >
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}
          </select>
        </label>
      )}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={submit} disabled={saving}>Duyệt</button>
        <button className="btn-outline" onClick={onClose}>Hủy</button>
      </div>
    </Modal>
  )
}

function RejectModal({ candidate, open, onClose, onDone }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) { setReason(''); setError('') }
  }, [open])

  async function submit() {
    setSaving(true)
    setError('')
    try {
      await api.post(`/employees/probation-exam-candidates/${candidate.id}/reject/`, { reason })
      onDone()
    } catch (err) {
      setError(err.response?.data?.detail || 'Từ chối thất bại.')
    } finally {
      setSaving(false)
    }
  }

  if (!candidate) return null

  return (
    <Modal open={open} title={`Từ chối - ${candidate.employee_name}`} onClose={onClose}>
      <label style={{ display: 'block', marginBottom: 8 }}>
        Lý do (tùy chọn)
        <textarea style={{ ...s.input, width: '100%', minHeight: 80 }} value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={submit} disabled={saving}>Từ chối</button>
        <button className="btn-outline" onClick={onClose}>Hủy</button>
      </div>
    </Modal>
  )
}

export default function ProbationExamApprovalPage() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [approveTarget, setApproveTarget] = useState(null)
  const [rejectTarget, setRejectTarget] = useState(null)

  function load() {
    api.get('/employees/probation-exam-candidates/', { params: { status: 'pending_approval' } })
      .then(({ data }) => setRows(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được danh sách.'))
  }

  useEffect(() => { load() }, [])

  function handleDone() {
    setApproveTarget(null)
    setRejectTarget(null)
    load()
  }

  return (
    <AppShell>
      <h2>Chờ duyệt thi</h2>
      <p className="muted-note" style={{ marginTop: -6 }}>
        Nhân sự đã hoàn thành LMS + checklist đào tạo 100% và có đề thi kết thúc thử việc khớp vị trí, đang chờ duyệt.
      </p>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!rows && !error && <p className="muted-note">Đang tải...</p>}
      {rows && (
        <Table>
          <thead>
            <tr><th>Mã NV</th><th>Họ tên</th><th>Nhà hàng</th><th>Vị trí</th><th>Đề thi</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.employee_code}</td>
                <td>{r.employee_name}</td>
                <td>{r.restaurant_name}</td>
                <td>{r.position}</td>
                <td>{r.assessment_title}</td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button className="btn-sm" onClick={() => setApproveTarget(r)}>Duyệt</button>
                  <button className="btn-outline btn-sm" onClick={() => setRejectTarget(r)}>Từ chối</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="muted-note">Không có ai đang chờ duyệt.</td></tr>
            )}
          </tbody>
        </Table>
      )}

      <ApproveModal candidate={approveTarget} open={!!approveTarget} onClose={() => setApproveTarget(null)} onDone={handleDone} />
      <RejectModal candidate={rejectTarget} open={!!rejectTarget} onClose={() => setRejectTarget(null)} onDone={handleDone} />
    </AppShell>
  )
}
