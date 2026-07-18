import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import ProgressBar from '../components/ProgressBar'
import Table from '../components/Table'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'

// Panel "Quản trị nhân sự" (đổi trạng thái, xuất phiếu...) chỉ dành cho Admin/OM.
// Trainer/BQL/AM/KCS chỉ xem chi tiết + checklist, không hiện phần quản trị nhiều thông tin.
const ADMIN_ROLES = new Set(['admin', 'om'])
// Đổi trạng thái làm việc: Admin/OM (panel đầy đủ) và cả BQL/Trainer (chỉ control gọn).
const STATUS_UPDATE_ROLES = new Set(['admin', 'om', 'bql', 'trainer'])
const COUNCIL_FINALIZE_ROLES = new Set(['admin', 'om', 'am', 'kcs'])

const CHECKLIST_STATUS_VARIANTS = { pending: 'neutral', in_progress: 'mint', done: 'success' }
const CHECKLIST_STATUS_LABELS = { pending: 'Chưa bắt đầu', in_progress: 'Đang thực hiện', done: 'Hoàn thành' }

const STATUS_OPTIONS = [
  { value: 'probation', label: 'Thử việc' },
  { value: 'active', label: 'Chính thức' },
  { value: 'resigned', label: 'Nghỉ việc' },
]

function resultBadgeVariant(result) {
  const r = (result || '').toLowerCase()
  if (r.includes('pass') || (r.includes('đạt') && !r.includes('không'))) return 'success'
  if (r.includes('không đạt')) return 'danger'
  return 'neutral'
}

export default function StudentDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [statusValue, setStatusValue] = useState('')
  const [saving, setSaving] = useState(false)

  const role = (user.role || '').toLowerCase()
  const isBod = role === 'bod'
  const isAdminPanel = ADMIN_ROLES.has(role)
  const canUpdateStatus = STATUS_UPDATE_ROLES.has(role)
  const canFinalizeCouncil = COUNCIL_FINALIZE_ROLES.has(role)

  function load() {
    api
      .get(`/employees/${id}/detail/`)
      .then(({ data }) => {
        setData(data)
        setStatusValue(data.info.work_status)
      })
      .catch(() => setError('Không tải được thông tin học viên.'))
  }

  useEffect(load, [id])

  async function saveStatus() {
    setSaving(true)
    setMessage('')
    try {
      await api.post(`/employees/${id}/change-status/`, { employee_status: statusValue })
      setMessage('Đã cập nhật trạng thái.')
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Không lưu được trạng thái.')
    } finally {
      setSaving(false)
    }
  }

  async function exportProbationResult() {
    setSaving(true)
    setMessage('')
    try {
      await api.post(`/employees/${id}/export-probation-result/`)
      setMessage('Đã xuất phiếu.')
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Không xuất được phiếu.')
    } finally {
      setSaving(false)
    }
  }

  async function finalizeCouncil() {
    setSaving(true)
    setMessage('')
    try {
      await api.post('/evaluation/council/finalize/', { employee: id })
      setMessage('Đã chốt kết quả hội đồng.')
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Không chốt được hội đồng.')
    } finally {
      setSaving(false)
    }
  }

  if (error) {
    return (
      <AppShell>
        <p style={{ color: 'var(--danger)' }}>{error}</p>
      </AppShell>
    )
  }
  if (!data) {
    return (
      <AppShell>
        <p className="muted-note">Đang tải...</p>
      </AppShell>
    )
  }

  const { info, progress, checklist, lms, evaluations, council } = data

  return (
    <AppShell>
      <div style={{ marginBottom: 12 }}>
        <Link to="/employees">← Quay lại danh sách</Link>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <h2 style={{ margin: 0 }}>
              {info.name} - {info.code}
            </h2>
            <div className="muted-note">
              {info.position} · {info.restaurant} {info.brand ? `· ${info.brand}` : ''}
            </div>
            <div className="muted-note">
              Ngày vào: {info.start_date || '—'} · Trainer: {info.trainer_name || '—'}
            </div>
          </div>
          <Badge variant={resultBadgeVariant(info.probation_result)}>{info.probation_result || 'Chưa có kết quả'}</Badge>
        </div>
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span>Tiến độ đào tạo</span>
            <span>
              {progress.done}/{progress.total} ({progress.percent}%)
            </span>
          </div>
          <ProgressBar percent={progress.percent} />
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Badge variant={lms.course_done ? 'success' : 'neutral'}>
            LMS: {lms.course_done ? 'Đã hoàn thành khóa' : 'Chưa xong khóa'}
          </Badge>
          <Badge variant="neutral">Cấp {info.level_group || '—'}</Badge>
          <Badge variant="neutral">Thử việc {info.probation_days ?? '—'} ngày</Badge>
        </div>
      </div>

      {isAdminPanel && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Quản trị nhân sự</h3>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={statusValue} onChange={(e) => setStatusValue(e.target.value)}>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <button onClick={saveStatus} disabled={saving}>
              Cập nhật trạng thái
            </button>
            {(info.probation_result || '').startsWith('Pass') && (
              <button className="btn-outline" onClick={exportProbationResult} disabled={saving}>
                {info.probation_result_pdf_url ? 'Xuất lại phiếu kết quả thử việc (PDF)' : 'Xuất phiếu kết quả thử việc (PDF)'}
              </button>
            )}
          </div>
          {info.probation_result_pdf_url && (
            <p style={{ marginTop: 8 }}>
              <Badge variant="success">Đã xuất phiếu</Badge>{' '}
              <a href={info.probation_result_pdf_url} target="_blank" rel="noreferrer">
                Xem phiếu kết quả thử việc
              </a>
            </p>
          )}
          {message && <p style={{ marginTop: 8 }}>{message}</p>}
        </div>
      )}

      {!isAdminPanel && canUpdateStatus && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Cập nhật trạng thái làm việc</h3>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={statusValue} onChange={(e) => setStatusValue(e.target.value)}>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <button onClick={saveStatus} disabled={saving}>
              Cập nhật
            </button>
          </div>
          {message && <p style={{ marginTop: 8 }}>{message}</p>}
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Checklist nội dung đào tạo</h3>
        {checklist.length === 0 && <p className="muted-note">Chưa có checklist phù hợp.</p>}
        {checklist.length > 0 && (
          <Table>
            <thead>
              <tr>
                <th>Nội dung</th>
                <th>Ngày</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {checklist.map((c) => (
                <tr key={c.checklist_id}>
                  <td>
                    {c.name}
                    <div className="muted-note" style={{ fontSize: 12 }}>
                      {c.category}
                    </div>
                  </td>
                  <td>{c.day ?? '—'}</td>
                  <td>
                    <Badge variant={CHECKLIST_STATUS_VARIANTS[c.status]}>{CHECKLIST_STATUS_LABELS[c.status]}</Badge>
                  </td>
                  <td>
                    {c.pdf_url ? (
                      <a href={c.pdf_url} target="_blank" rel="noreferrer">
                        Xem
                      </a>
                    ) : (
                      !isBod && <Link to="/training">Đào tạo</Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Kết quả học & thi LMS</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div className="stat-label">Khóa học</div>
            {lms.courses.length === 0 && <p className="muted-note">Chưa có dữ liệu.</p>}
            {lms.courses.map((c, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '4px 0' }}>
                <span>{c.name}</span>
                <Badge variant={c.status === 'Đạt' ? 'success' : 'neutral'}>{c.status || '—'}</Badge>
              </div>
            ))}
          </div>
          <div>
            <div className="stat-label">Bài thi</div>
            {lms.exams.length === 0 && <p className="muted-note">Chưa có dữ liệu.</p>}
            {lms.exams.map((e, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '4px 0' }}>
                <span>
                  {e.name} (lần {e.attempt})
                </span>
                <Badge variant={e.passed ? 'success' : 'danger'}>{e.score ?? '—'} điểm</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Các bài đánh giá</h3>
        {evaluations.length === 0 && <p className="muted-note">Chưa có đánh giá nào.</p>}
        {evaluations.length > 0 && (
          <Table>
            <thead>
              <tr>
                <th>Loại</th>
                <th>Ngày</th>
                <th>%</th>
                <th>Kết quả</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {evaluations.map((ev) => (
                <tr key={ev.id}>
                  <td>{ev.eval_type}</td>
                  <td>{ev.date || '—'}</td>
                  <td>{ev.percent}%</td>
                  <td>
                    <Badge variant={ev.result === 'pass' ? 'success' : 'danger'}>
                      {ev.result === 'pass' ? 'Đạt' : 'Không đạt'}
                    </Badge>
                  </td>
                  <td>
                    {ev.pdf_url && (
                      <a href={ev.pdf_url} target="_blank" rel="noreferrer">
                        PDF
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>

      {council && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Hội đồng đánh giá</h3>
          {!council.is_council_position && <p className="muted-note">Vị trí này không thuộc diện Hội đồng.</p>}
          {council.is_council_position && (
            <>
              <div className="muted-note">{council.judge_count} giám khảo đã chấm</div>
              <div className="stat-num" style={{ margin: '8px 0' }}>
                {council.overall}%
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {council.aspects.map((a) => (
                  <div key={a.id}>
                    <div className="muted-note" style={{ fontSize: 12 }}>
                      {a.name}
                    </div>
                    <ProgressBar percent={a.avg} />
                    <div style={{ fontSize: 12 }}>{a.avg}%</div>
                  </div>
                ))}
              </div>
              {!isBod && (
                <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                  <Link to="/evaluation">
                    <button className="btn-outline btn-sm">Chấm điểm</button>
                  </Link>
                  {canFinalizeCouncil && (
                    <button className="btn-sm" onClick={finalizeCouncil} disabled={saving || council.judge_count < 2}>
                      Chốt hội đồng
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </AppShell>
  )
}
