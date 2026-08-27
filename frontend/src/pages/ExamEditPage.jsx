import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import CompetencySelect from '../components/CompetencySelect'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import { DIFFICULTIES, typeLabel } from '../config/examQuestionTypes'
import { usePaginatedList } from '../hooks/usePaginatedList'
import { useCompetencyOptions } from '../hooks/useCompetencyOptions'
import * as s from './listPageStyles'

const SHOW_RESULT_MODES = [
  { value: 'immediately', label: 'Hiện ngay sau khi nộp' },
  { value: 'after_close', label: 'Hiện sau khi đề đóng (lưu trữ)' },
  { value: 'score_only', label: 'Chỉ hiện điểm, không hiện đáp án' },
]

const REVIEW_MODES = [
  { value: 'none', label: 'Không' },
  { value: 'score_only', label: 'Không chi tiết điểm' },
  { value: 'full_detail', label: 'Chi tiết điểm từng câu' },
]

const PROCTORING_EVENT_LABELS = {
  no_face: 'Không thấy khuôn mặt', multi_face: 'Nhiều hơn 1 khuôn mặt', tab_leave: 'Rời tab',
  blur: 'Mất focus cửa sổ', snapshot: 'Ảnh chụp định kỳ', fullscreen_exit: 'Thoát toàn màn hình',
}

function ProctoringEvidenceModal({ attemptId, open, onClose, onFlagged }) {
  const [timeline, setTimeline] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !attemptId) return
    setTimeline(null)
    setError('')
    api.get(`/exams/attempts/${attemptId}/proctoring/`)
      .then(({ data }) => setTimeline(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được bằng chứng.'))
  }, [open, attemptId])

  async function toggleFlag() {
    const { data } = await api.post(`/exams/attempts/${attemptId}/flag/`, { flagged: !timeline.flagged_suspicious })
    setTimeline((t) => ({ ...t, flagged_suspicious: data.flagged_suspicious }))
    onFlagged()
  }

  return (
    <Modal open={open} title="Bằng chứng giám sát thi" onClose={onClose}>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!timeline && !error && <p className="muted-note">Đang tải...</p>}
      {timeline && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <span className="badge badge-warning">Chỉ số nghi vấn: {timeline.suspicion_score}</span>
            <span className="muted-note" style={{ fontSize: 12 }}>
              Rời tab {timeline.counts.tab_leave} · Không thấy mặt {timeline.counts.no_face} · Nhiều mặt {timeline.counts.multi_face}
            </span>
            <button className={timeline.flagged_suspicious ? '' : 'btn-outline'} onClick={toggleFlag} style={{ marginLeft: 'auto' }}>
              {timeline.flagged_suspicious ? '✓ Đã đánh dấu nghi vấn' : 'Đánh dấu nghi vấn'}
            </button>
          </div>
          {timeline.supervised_by_restaurant_camera && (
            <p className="muted-note" style={{ marginTop: -4 }}>
              Giám sát qua camera nhà hàng — Người coi thi:{' '}
              {timeline.proctors.length > 0 ? timeline.proctors.map((p) => p.name).join(', ') : 'chưa phân công'}
            </p>
          )}
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {timeline.events.map((e) => (
              <div key={e.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--card-border)' }}>
                <span className="muted-note" style={{ fontSize: 12, minWidth: 130 }}>
                  {new Date(e.created_at).toLocaleString('vi-VN')}
                </span>
                <span className="badge badge-neutral">{PROCTORING_EVENT_LABELS[e.type] || e.type}</span>
                {e.detail && <span className="muted-note" style={{ fontSize: 12 }}>{e.detail}</span>}
                {e.image_url && (
                  <a href={e.image_url} target="_blank" rel="noreferrer">
                    <img src={e.image_url} alt="Ảnh chụp" style={{ height: 48, borderRadius: 4 }} />
                  </a>
                )}
              </div>
            ))}
            {timeline.events.length === 0 && <p className="muted-note">Chưa có sự kiện nào được ghi.</p>}
          </div>
        </>
      )}
    </Modal>
  )
}

function useDragReorder(items, onDrop) {
  const dragIndex = useRef(null)
  return {
    onDragStart: (i) => () => { dragIndex.current = i },
    onDragOver: (e) => e.preventDefault(),
    onDropAt: (i) => () => {
      const from = dragIndex.current
      dragIndex.current = null
      if (from === null || from === i) return
      const next = [...items]
      const [moved] = next.splice(from, 1)
      next.splice(i, 0, moved)
      onDrop(next)
    },
  }
}

function QuestionPickerModal({ open, onClose, existingIds, onAdded }) {
  const [bankId, setBankId] = useState('')
  const [selected, setSelected] = useState([])
  const [questions, setQuestions] = useState([])
  const [saving, setSaving] = useState(false)

  const { data: banks } = usePaginatedList('/exams/banks/', { page_size: 100 })

  useEffect(() => {
    setSelected([])
    if (!bankId) {
      setQuestions([])
      return
    }
    api.get('/exams/questions/', { params: { bank: bankId, page_size: 200 } })
      .then(({ data }) => setQuestions(data.results))
  }, [bankId])

  function toggle(qid) {
    setSelected((prev) => (prev.includes(qid) ? prev.filter((x) => x !== qid) : [...prev, qid]))
  }

  async function addSelected() {
    setSaving(true)
    try {
      for (const qid of selected) {
        // eslint-disable-next-line no-await-in-loop
        await onAdded(qid)
      }
      setSelected([])
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} title="Thêm câu hỏi vào đề" onClose={onClose}>
      <select value={bankId} onChange={(e) => setBankId(e.target.value)} style={{ ...s.select, width: '100%', marginBottom: 8 }}>
        <option value="">— Chọn ngân hàng câu hỏi —</option>
        {banks.results.map((b) => (
          <option key={b.id} value={b.id}>{b.name}</option>
        ))}
      </select>
      {bankId && (
        <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: 6 }}>
          {questions.map((q) => (
            <label
              key={q.id}
              style={{
                display: 'flex', gap: 8, alignItems: 'center', padding: 8,
                borderBottom: '1px solid var(--card-border)', opacity: existingIds.includes(q.id) ? 0.5 : 1,
              }}
            >
              <input
                type="checkbox" checked={selected.includes(q.id)} disabled={existingIds.includes(q.id)}
                onChange={() => toggle(q.id)}
              />
              <span className="badge badge-neutral">{typeLabel(q.type)}</span>
              <span style={{ flex: 1 }}>{q.stem_html}</span>
              {existingIds.includes(q.id) && <span className="muted-note">(đã có trong đề)</span>}
            </label>
          ))}
          {questions.length === 0 && <p className="muted-note" style={{ padding: 8 }}>Ngân hàng chưa có câu hỏi.</p>}
        </div>
      )}
      <div style={{ marginTop: 12 }}>
        <button onClick={addSelected} disabled={saving || selected.length === 0}>
          Thêm {selected.length > 0 ? `(${selected.length})` : ''}
        </button>
      </div>
    </Modal>
  )
}

function AssignModal({ assessmentId, open, onClose }) {
  const [mode, setMode] = useState('individual')
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState([])
  const [position, setPosition] = useState('')
  const [restaurantId, setRestaurantId] = useState('')
  const [group, setGroup] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })

  useEffect(() => {
    if (!search) {
      setResults([])
      return
    }
    const timeout = setTimeout(() => {
      api.get('/employees/', { params: { search, page_size: 10 } }).then(({ data }) => setResults(data.results))
    }, 300)
    return () => clearTimeout(timeout)
  }, [search])

  function addSelected(emp) {
    if (selected.some((e) => e.id === emp.id)) return
    setSelected((prev) => [...prev, emp])
    setSearch('')
    setResults([])
  }

  async function submit() {
    setSaving(true)
    setError('')
    setMessage('')
    const payload =
      mode === 'individual'
        ? { employee_ids: selected.map((e) => e.id) }
        : { position: position || undefined, restaurant_id: restaurantId || undefined, group: group || undefined }
    try {
      const { data } = await api.post(`/exams/assessments/${assessmentId}/assign/`, payload)
      setMessage(`Đã gán cho ${data.created} nhân sự mới.`)
      setSelected([])
    } catch (err) {
      setError(err.response?.data?.detail || 'Không gán được đề thi.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} title="Gán đề thi" onClose={onClose}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button className={mode === 'individual' ? '' : 'btn-outline'} onClick={() => setMode('individual')}>
          Theo cá nhân
        </button>
        <button className={mode === 'filter' ? '' : 'btn-outline'} onClick={() => setMode('filter')}>
          Theo vị trí / nhà hàng
        </button>
      </div>

      {mode === 'individual' ? (
        <>
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
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
                <span style={{ cursor: 'pointer' }} onClick={() => setSelected((prev) => prev.filter((x) => x.id !== e.id))}>
                  ✕
                </span>
              </span>
            ))}
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            value={position} onChange={(e) => setPosition(e.target.value)}
            placeholder="Vị trí (vd Phục vụ) - để trống nếu không lọc" style={s.input}
          />
          <select value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)} style={s.select}>
            <option value="">Tất cả nhà hàng</option>
            {restaurantOptions.results.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
          <input
            value={group} onChange={(e) => setGroup(e.target.value)}
            placeholder="Nhóm cấp (level_group, vd S/O/P) - để trống nếu không lọc" style={s.input}
          />
        </div>
      )}

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {message && <p style={{ color: 'var(--forest-dark)' }}>{message}</p>}
      <div style={{ marginTop: 12 }}>
        <button onClick={submit} disabled={saving}>Gán đề thi</button>
      </div>
    </Modal>
  )
}

export default function ExamEditPage() {
  const { id } = useParams()
  const competencyOptions = useCompetencyOptions()
  const [assessment, setAssessment] = useState(null)
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [assignOpen, setAssignOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [tab, setTab] = useState('settings')
  const [randomMode, setRandomMode] = useState(false)
  const [evidenceAttemptId, setEvidenceAttemptId] = useState(null)
  const [bankId, setBankId] = useState('')
  const [count, setCount] = useState(10)
  const [difficulty, setDifficulty] = useState('')

  const { data: banks } = usePaginatedList('/exams/banks/', { page_size: 100 })

  function load() {
    api.get(`/exams/assessments/${id}/`)
      .then(({ data }) => {
        setAssessment(data)
        setRandomMode(!!data.random_pool_config)
        setBankId(data.random_pool_config?.bank_id || '')
        setCount(data.random_pool_config?.count || 10)
        setDifficulty(data.random_pool_config?.difficulty || '')
      })
      .catch(() => setError('Không tải được đề thi.'))
    api.get(`/exams/assessments/${id}/results/`).then(({ data }) => setResults(data)).catch(() => {})
  }

  useEffect(load, [id])

  const aQuestions = assessment?.assessment_questions || []
  const questionDrag = useDragReorder(aQuestions, (next) => {
    const items = next.map((aq, i) => ({ id: aq.id, order: i }))
    api.post('/exams/reorder/', { items }).then(load)
  })

  async function updateField(field, value) {
    await api.patch(`/exams/assessments/${id}/`, { [field]: value })
    load()
  }

  async function saveRandomConfig() {
    await api.patch(`/exams/assessments/${id}/`, {
      random_pool_config: bankId ? { bank_id: Number(bankId), count: Number(count) || 1, difficulty: difficulty || undefined } : null,
    })
    load()
  }

  async function toggleMode(useRandom) {
    setRandomMode(useRandom)
    if (!useRandom) {
      await api.patch(`/exams/assessments/${id}/`, { random_pool_config: null })
      load()
    }
  }

  async function addQuestion(questionId) {
    await api.post('/exams/assessment-questions/', { assessment: id, question: questionId, order: aQuestions.length })
  }

  async function removeQuestion(aqId) {
    await api.delete(`/exams/assessment-questions/${aqId}/`)
    load()
  }

  async function updatePoints(aqId, value) {
    await api.patch(`/exams/assessment-questions/${aqId}/`, {
      points_override: value === '' ? null : Number(value),
    })
    load()
  }

  async function exportExcel() {
    const resp = await api.get(`/exams/assessments/${id}/results/export/`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `ket_qua_${id}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  if (error) return <AppShell><p style={{ color: 'var(--danger)' }}>{error}</p></AppShell>
  if (!assessment) return <AppShell><p className="muted-note">Đang tải...</p></AppShell>

  return (
    <AppShell>
      <Link to="/exams-admin">&larr; Danh sách đề thi</Link>
      <h2 style={{ marginTop: 8 }}>{assessment.title}</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button className={tab === 'settings' ? '' : 'btn-outline'} onClick={() => setTab('settings')}>
          Thiết lập
        </button>
        <button className={tab === 'custom' ? '' : 'btn-outline'} onClick={() => setTab('custom')}>
          Tùy chỉnh
        </button>
      </div>

      {tab === 'custom' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p className="muted-note" style={{ marginTop: 0 }}>Thiết lập đề (kiểu CLS) — áp dụng cho lần làm bài tiếp theo.</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
            <label style={{ fontSize: 13 }}>
              Số câu/trang{' '}
              <input
                type="number" defaultValue={assessment.questions_per_page || ''}
                onBlur={(e) => updateField('questions_per_page', e.target.value ? Number(e.target.value) : null)}
                style={{ ...s.input, width: 90 }} placeholder="Tất cả 1 trang"
              />
            </label>
            <label style={{ fontSize: 13 }}>
              Chế độ xem lại{' '}
              <select
                value={assessment.review_mode} onChange={(e) => updateField('review_mode', e.target.value)}
                style={s.select}
              >
                {REVIEW_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </label>
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
              <input
                type="checkbox" checked={assessment.show_countdown}
                onChange={(e) => updateField('show_countdown', e.target.checked)}
              /> Đếm ngược thời gian
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
              <input
                type="checkbox" checked={assessment.show_score}
                onChange={(e) => updateField('show_score', e.target.checked)}
              /> Hiển thị điểm của thí sinh
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
              <input
                type="checkbox" checked={assessment.show_grade_label}
                onChange={(e) => updateField('show_grade_label', e.target.checked)}
              /> Hiển thị xếp loại
            </label>
          </div>

          <hr style={{ margin: '16px 0', border: 'none', borderTop: '1px solid var(--card-border)' }} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <input
              type="checkbox" checked={assessment.proctoring_enabled}
              onChange={(e) => updateField('proctoring_enabled', e.target.checked)}
            /> Giám sát thi (webcam + chặn rời tab/copy-paste)
          </label>
          {assessment.proctoring_enabled && (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
              <label style={{ fontSize: 13 }}>
                Chụp ảnh mỗi (giây){' '}
                <input
                  type="number" defaultValue={assessment.proctoring_snapshot_interval_sec}
                  onBlur={(e) => updateField('proctoring_snapshot_interval_sec', Number(e.target.value) || 45)}
                  style={{ ...s.input, width: 90 }}
                />
              </label>
              <label style={{ fontSize: 13 }}>
                Tự nộp sau (lần rời tab){' '}
                <input
                  type="number" defaultValue={assessment.tab_leave_auto_submit_limit || ''}
                  onBlur={(e) => updateField('tab_leave_auto_submit_limit', e.target.value ? Number(e.target.value) : null)}
                  style={{ ...s.input, width: 90 }} placeholder="Không tự nộp"
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                <input
                  type="checkbox" checked={assessment.require_fullscreen}
                  onChange={(e) => updateField('require_fullscreen', e.target.checked)}
                /> Yêu cầu toàn màn hình
              </label>
            </div>
          )}
          <label style={{ display: 'block', fontSize: 13 }}>
            Mật khẩu vào đề {assessment.has_password && <span className="badge badge-neutral">Đã đặt</span>}
          </label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <input
              type="text" placeholder="Để trống = không yêu cầu mật khẩu"
              onBlur={(e) => { if (e.target.value) { updateField('access_password', e.target.value); e.target.value = '' } }}
              style={{ ...s.input, flex: 1 }}
            />
            {assessment.has_password && (
              <button className="btn-outline btn-sm" onClick={() => updateField('access_password', '')}>Xoá mật khẩu</button>
            )}
          </div>
          <p className="muted-note" style={{ marginTop: 4 }}>Nhập mật khẩu mới rồi rời khỏi ô để lưu.</p>
        </div>
      )}

      {tab === 'settings' && (
      <div className="card" style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Tên đề thi</label>
        <input
          defaultValue={assessment.title}
          onBlur={(e) => e.target.value !== assessment.title && updateField('title', e.target.value)}
          style={{ ...s.input, width: '100%', marginBottom: 8 }}
        />
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Mô tả</label>
        <textarea
          defaultValue={assessment.description}
          onBlur={(e) => e.target.value !== assessment.description && updateField('description', e.target.value)}
          style={{ width: '100%', minHeight: 50, marginBottom: 8 }}
        />
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>
            Thời gian (phút){' '}
            <input
              type="number" defaultValue={assessment.time_limit_min || ''}
              onBlur={(e) => updateField('time_limit_min', e.target.value ? Number(e.target.value) : null)}
              style={{ ...s.input, width: 90 }} placeholder="Không giới hạn"
            />
          </label>
          <label style={{ fontSize: 13 }}>
            Điểm đạt (%){' '}
            <input
              type="number" defaultValue={assessment.pass_mark}
              onBlur={(e) => updateField('pass_mark', Number(e.target.value) || 0)}
              style={{ ...s.input, width: 90 }}
            />
          </label>
          <label style={{ fontSize: 13 }}>
            Số lần làm tối đa{' '}
            <input
              type="number" defaultValue={assessment.max_attempts}
              onBlur={(e) => updateField('max_attempts', Number(e.target.value) || 1)}
              style={{ ...s.input, width: 90 }}
            />
          </label>
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
            <input
              type="checkbox" checked={assessment.shuffle_questions}
              onChange={(e) => updateField('shuffle_questions', e.target.checked)}
            /> Trộn câu hỏi
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
            <input
              type="checkbox" checked={assessment.shuffle_options}
              onChange={(e) => updateField('shuffle_options', e.target.checked)}
            /> Trộn đáp án
          </label>
          <label style={{ fontSize: 13 }}>
            Hiện kết quả{' '}
            <select
              value={assessment.show_result_mode}
              onChange={(e) => updateField('show_result_mode', e.target.value)}
              style={s.select}
            >
              {SHOW_RESULT_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </label>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ fontSize: 13, color: 'var(--muted)' }}>Trạng thái</label>
          <select value={assessment.status} onChange={(e) => updateField('status', e.target.value)} style={s.select}>
            <option value="draft">Nháp</option>
            <option value="published">Xuất bản</option>
            <option value="archived">Lưu trữ (đóng đề)</option>
          </select>
          <button onClick={() => setAssignOpen(true)}>Gán đề thi</button>
          <button className="btn-outline" onClick={exportExcel}>Xuất Excel kết quả</button>
        </div>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
          Năng lực (dùng để tính điểm Hồ sơ 360)
        </label>
        <CompetencySelect
          value={assessment.competency}
          onChange={(v) => updateField('competency', v)}
          options={competencyOptions}
          style={{ width: '100%' }}
        />
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
          Mã đồng bộ hồ sơ (sync_exam_type) — để trống = không đồng bộ ExamResult
        </label>
        <input
          defaultValue={assessment.sync_exam_type}
          onBlur={(e) => e.target.value !== assessment.sync_exam_type && updateField('sync_exam_type', e.target.value)}
          placeholder="vd 15N..." style={{ ...s.input, width: '100%' }}
        />
      </div>
      )}

      <h3>Câu hỏi trong đề</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button className={!randomMode ? '' : 'btn-outline'} onClick={() => toggleMode(false)}>Chọn tay</button>
        <button className={randomMode ? '' : 'btn-outline'} onClick={() => toggleMode(true)}>Ngẫu nhiên từ ngân hàng</button>
      </div>

      {randomMode ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <select value={bankId} onChange={(e) => setBankId(e.target.value)} style={s.select}>
              <option value="">— Chọn ngân hàng câu hỏi —</option>
              {banks.results.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <input
              type="number" value={count} onChange={(e) => setCount(e.target.value)}
              placeholder="Số câu" style={{ ...s.input, width: 90 }}
            />
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} style={s.select}>
              <option value="">Mọi độ khó</option>
              {DIFFICULTIES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
            </select>
            <button onClick={saveRandomConfig} disabled={!bankId}>Lưu cài đặt rút ngẫu nhiên</button>
          </div>
          <p className="muted-note" style={{ marginTop: 8 }}>
            Mỗi lần làm bài sẽ rút ngẫu nhiên {count} câu từ ngân hàng đã chọn.
          </p>
        </div>
      ) : (
        <>
          {aQuestions.map((aq, i) => (
            <div
              key={aq.id} draggable
              onDragStart={questionDrag.onDragStart(i)}
              onDragOver={questionDrag.onDragOver}
              onDrop={questionDrag.onDropAt(i)}
              className="card"
              style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, cursor: 'grab' }}
            >
              <span>⠿</span>
              <span className="badge badge-neutral">{typeLabel(aq.question_detail?.type)}</span>
              <span style={{ flex: 1 }}>{aq.question_detail?.stem_html}</span>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                Điểm{' '}
                <input
                  type="number" defaultValue={aq.points_override ?? aq.question_detail?.points ?? ''}
                  onBlur={(e) => updatePoints(aq.id, e.target.value)}
                  style={{ ...s.input, width: 64 }}
                />
              </label>
              <button className="btn-outline btn-sm" onClick={() => removeQuestion(aq.id)}>Xóa khỏi đề</button>
            </div>
          ))}
          {aQuestions.length === 0 && <p className="muted-note">Chưa có câu hỏi nào trong đề.</p>}
          <button className="btn-outline" onClick={() => setPickerOpen(true)}>+ Thêm câu hỏi</button>
        </>
      )}

      <h3 style={{ marginTop: 24 }}>Kết quả</h3>
      <Table>
        <thead>
          <tr>
            <th>Nhân sự</th><th>Lần</th><th>Điểm</th><th>%</th><th>Đạt</th><th>Trạng thái</th><th>Nộp lúc</th>
            {assessment.proctoring_enabled && <th>Giám sát</th>}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={r.id}>
              <td>{r.employee_code} — {r.employee_name}</td>
              <td>{r.attempt_no}</td>
              <td>{r.score ?? '-'}/{r.max_score ?? '-'}</td>
              <td>{r.percent ?? '-'}</td>
              <td>{r.passed === null ? '-' : r.passed ? <Badge variant="success">Đạt</Badge> : <Badge variant="danger">Chưa đạt</Badge>}</td>
              <td>{r.status_display}</td>
              <td>{r.submitted_at ? new Date(r.submitted_at).toLocaleString('vi-VN') : '-'}</td>
              {assessment.proctoring_enabled && (
                <td>
                  {r.flagged_suspicious && <Badge variant="danger">Nghi vấn</Badge>}{' '}
                  <button className="btn-outline btn-sm" onClick={() => setEvidenceAttemptId(r.id)}>
                    Bằng chứng ({r.proctoring_event_count})
                  </button>
                </td>
              )}
            </tr>
          ))}
          {results.length === 0 && (
            <tr><td colSpan={assessment.proctoring_enabled ? 8 : 7} className="muted-note">Chưa có ai làm bài.</td></tr>
          )}
        </tbody>
      </Table>

      <AssignModal assessmentId={id} open={assignOpen} onClose={() => setAssignOpen(false)} />
      <QuestionPickerModal
        open={pickerOpen} onClose={() => setPickerOpen(false)}
        existingIds={aQuestions.map((aq) => aq.question)}
        onAdded={async (qid) => { await addQuestion(qid); load() }}
      />
      <ProctoringEvidenceModal
        attemptId={evidenceAttemptId} open={!!evidenceAttemptId}
        onClose={() => setEvidenceAttemptId(null)}
        onFlagged={load}
      />
    </AppShell>
  )
}
