import { Fragment, useEffect, useState } from 'react'
import { X } from 'lucide-react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

// Man "Ky thi" (Prompt_NganHangDe_va_KyThi_kieuCLS.md muc 3) - khu "To chuc dao tao", tach khoi
// "Ngan hang de" (khu "Noi dung"). Tao Ky thi = chon 1 De + giao theo ca nhan/vi tri/nha hang/
// nhom + dat lich mo-dong -> sinh AssessmentAssignment (backend: services.create_exam_session).

function CreateSessionForm({ onCreated }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [assessmentId, setAssessmentId] = useState('')
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [mode, setMode] = useState('filter')
  const [position, setPosition] = useState('')
  const [restaurantId, setRestaurantId] = useState('')
  const [group, setGroup] = useState('')
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState([])
  const [supervised, setSupervised] = useState(false)
  const [proctorIds, setProctorIds] = useState([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const { data: assessments } = usePaginatedList('/exams/assessments/', { status: 'published', page_size: 100 })
  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })
  const { data: userOptions } = usePaginatedList('/auth/users/', { page_size: 200 })

  function searchEmployees(q) {
    setSearch(q)
    if (!q) {
      setResults([])
      return
    }
    api.get('/employees/', { params: { search: q, page_size: 10 } })
      .then(({ data }) => setResults(Array.isArray(data?.results) ? data.results : []))
  }

  function addSelected(emp) {
    if (selected.some((e) => e.id === emp.id)) return
    setSelected((prev) => [...prev, emp])
    setSearch('')
    setResults([])
  }

  async function submit() {
    if (!assessmentId) {
      setError('Chọn đề thi.')
      return
    }
    setSaving(true)
    setError('')
    const target =
      mode === 'individual'
        ? { employee_ids: selected.map((e) => e.id) }
        : { position: position || undefined, restaurant_id: restaurantId || undefined, group: group || undefined }
    try {
      await api.post('/exams/sessions/', {
        assessment: assessmentId, title: title.trim() || undefined,
        start_at: startAt ? new Date(startAt).toISOString() : null,
        end_at: endAt ? new Date(endAt).toISOString() : null,
        supervised_by_restaurant_camera: supervised,
        proctors: proctorIds,
        ...target,
      })
      setOpen(false)
      setTitle(''); setAssessmentId(''); setStartAt(''); setEndAt('')
      setPosition(''); setRestaurantId(''); setGroup(''); setSelected([])
      setSupervised(false); setProctorIds([])
      onCreated()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không tạo được kỳ thi.')
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return <button onClick={() => setOpen(true)}>+ Tạo Kỳ thi</button>
  }

  return (
    <div className="card" style={{ maxWidth: 640, marginBottom: 16 }}>
      <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Tên kỳ thi (tùy chọn, mặc định lấy tên đề)</label>
      <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ ...s.input, width: '100%', marginBottom: 8 }} />

      <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Đề thi *</label>
      <select value={assessmentId} onChange={(e) => setAssessmentId(e.target.value)} style={{ ...s.select, width: '100%', marginBottom: 8 }}>
        <option value="">— Chọn đề thi (đã xuất bản) —</option>
        {assessments.results.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
      </select>

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
      <p className="muted-note" style={{ marginTop: -4 }}>Để trống = không giới hạn thời gian mở/đóng.</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <button className={mode === 'filter' ? '' : 'btn-outline'} onClick={() => setMode('filter')}>Theo vị trí / nhà hàng</button>
        <button className={mode === 'individual' ? '' : 'btn-outline'} onClick={() => setMode('individual')}>Theo cá nhân</button>
      </div>

      {mode === 'filter' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
          <input
            value={position} onChange={(e) => setPosition(e.target.value)}
            placeholder="Vị trí (vd Phục vụ) - để trống nếu không lọc" style={s.input}
          />
          <select value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)} style={s.select}>
            <option value="">Tất cả nhà hàng</option>
            {restaurantOptions.results.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <input
            value={group} onChange={(e) => setGroup(e.target.value)}
            placeholder="Nhóm cấp (level_group) - để trống nếu không lọc" style={s.input}
          />
        </div>
      ) : (
        <div style={{ marginBottom: 8 }}>
          <input
            value={search} onChange={(e) => searchEmployees(e.target.value)}
            placeholder="Tìm nhân sự theo mã / tên..." style={{ ...s.input, width: '100%' }}
          />
          {results.length > 0 && (
            <div style={{ border: '1px solid var(--card-border)', borderRadius: 6, marginTop: 4 }}>
              {results.map((emp) => (
                <div key={emp.id} onClick={() => addSelected(emp)} style={{ padding: 8, cursor: 'pointer' }}>
                  {emp.code} — {emp.name} ({emp.position})
                </div>
              ))}
            </div>
          )}
          <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {selected.map((e) => (
              <span key={e.id} className="badge badge-neutral">
                {e.code}{' '}
                <span style={{ cursor: 'pointer', display: 'inline-flex', verticalAlign: 'middle' }} onClick={() => setSelected((prev) => prev.filter((x) => x.id !== e.id))}>
                  <X size={12} />
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

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
            {userOptions.results.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}
          </select>
        </label>
      )}

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={submit} disabled={saving}>Tạo Kỳ thi</button>
        <button className="btn-outline" onClick={() => setOpen(false)}>Hủy</button>
      </div>
    </div>
  )
}

function TrackingPanel({ sessionId }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    api.get(`/exams/sessions/${sessionId}/tracking/`).then(({ data }) => setRows(Array.isArray(data) ? data : []))
  }, [sessionId])

  async function exportExcel() {
    const resp = await api.get(`/exams/sessions/${sessionId}/tracking/export/`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `theo_doi_ky_thi_${sessionId}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return (
    <div style={{ padding: 12 }}>
      <button className="btn-outline btn-sm" onClick={exportExcel} style={{ marginBottom: 8 }}>Xuất Excel</button>
      <Table>
        <thead>
          <tr><th>Mã NV</th><th>Họ tên</th><th>Đã thi</th><th>Điểm</th><th>%</th><th>Đạt</th></tr>
        </thead>
        <tbody>
          {(rows || []).map((r) => (
            <tr key={r.employee_id}>
              <td>{r.employee_code}</td>
              <td>{r.employee_name}</td>
              <td>{r.done ? <Badge variant="success">Đã thi</Badge> : <Badge variant="neutral">Chưa thi</Badge>}</td>
              <td>{r.score ?? '-'}/{r.max_score ?? '-'}</td>
              <td>{r.percent ?? '-'}</td>
              <td>{r.passed === null ? '-' : r.passed ? <Badge variant="success">Đạt</Badge> : <Badge variant="danger">Chưa đạt</Badge>}</td>
            </tr>
          ))}
          {rows && rows.length === 0 && <tr><td colSpan={6} className="muted-note">Chưa giao cho ai.</td></tr>}
        </tbody>
      </Table>
    </div>
  )
}

export default function ExamSessionsPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [expandedId, setExpandedId] = useState(null)
  const { data, loading } = usePaginatedList('/exams/sessions/', { page_size: 50, refreshKey })

  return (
    <AppShell>
      <h2>Kỳ thi</h2>
      <p className="muted-note" style={{ marginTop: -6 }}>
        Chọn 1 đề thi, giao cho nhân sự (theo cá nhân/vị trí/nhà hàng/nhóm) và đặt lịch mở–đóng.
      </p>

      <div style={{ marginBottom: 16 }}>
        <CreateSessionForm onCreated={() => setRefreshKey((k) => k + 1)} />
      </div>

      {loading && <p className="muted-note">Đang tải...</p>}
      <Table>
        <thead>
          <tr>
            <th>Kỳ thi</th><th>Đề thi</th><th>Mở</th><th>Đóng</th><th>Đã gán</th><th>Đã thi</th>
          </tr>
        </thead>
        <tbody>
          {data.results.map((sess) => (
            <Fragment key={sess.id}>
              <tr style={{ cursor: 'pointer' }} onClick={() => setExpandedId(expandedId === sess.id ? null : sess.id)}>
                <td>
                  {sess.title}
                  {sess.supervised_by_restaurant_camera && (
                    <span style={{ marginLeft: 6 }}><Badge variant="warning">Giám sát camera</Badge></span>
                  )}
                </td>
                <td>{sess.assessment_title}</td>
                <td>{sess.start_at ? new Date(sess.start_at).toLocaleString('vi-VN') : '—'}</td>
                <td>{sess.end_at ? new Date(sess.end_at).toLocaleString('vi-VN') : '—'}</td>
                <td>{sess.assigned_count}</td>
                <td>{sess.done_count}</td>
              </tr>
              {expandedId === sess.id && (
                <tr>
                  <td colSpan={6} style={{ padding: 0, background: 'var(--card-bg-subtle, transparent)' }}>
                    <TrackingPanel sessionId={sess.id} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {data.results.length === 0 && (
            <tr><td colSpan={6} className="muted-note">Chưa có kỳ thi nào.</td></tr>
          )}
        </tbody>
      </Table>
    </AppShell>
  )
}
