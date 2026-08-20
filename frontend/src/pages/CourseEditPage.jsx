import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import CompetencySelect from '../components/CompetencySelect'
import Modal from '../components/Modal'
import PhotoSlot from '../components/PhotoSlot'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import { useCompetencyOptions } from '../hooks/useCompetencyOptions'
import * as s from './listPageStyles'

const LESSON_TYPES = [
  { value: 'video_r2', label: 'Video (tải lên R2)' },
  { value: 'video_youtube', label: 'Video YouTube' },
  { value: 'video_vimeo', label: 'Video Vimeo' },
  { value: 'pdf', label: 'PDF' },
  { value: 'text', label: 'Văn bản' },
  { value: 'link', label: 'Liên kết' },
  { value: 'scorm', label: 'SCORM (Articulate 360...)' },
]
const COMPLETE_RULES = [
  { value: 'mark', label: 'Tự đánh dấu hoàn thành' },
  { value: 'open', label: 'Mở bài là xong' },
  { value: 'watch_pct', label: 'Xem đủ % video' },
]

// Sap xep lai 1 danh sach bang keo-tha HTML5 thuan (khong them thu vien moi) - tra ve handler
// gan vao thuoc tinh draggable cua tung dong + ham goi khi tha xong.
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

function ScormUploadWidget({ lesson, onUploaded }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [justUploaded, setJustUploaded] = useState(null)

  async function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setError('')
    const formData = new FormData()
    formData.append('lesson', lesson.id)
    formData.append('file', file)
    try {
      const { data } = await api.post('/courses/scorm/upload/', formData)
      setJustUploaded(data)
      onUploaded(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không tải lên được gói SCORM.')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const pkg = justUploaded || lesson.scorm_package

  return (
    <div style={{ marginBottom: 8 }}>
      {pkg ? (
        <p className="muted-note" style={{ marginBottom: 4 }}>
          Đã có gói: {pkg.title || '(không có tên)'} · {pkg.version_display} · file khởi chạy: {pkg.launch_path}
        </p>
      ) : (
        <p className="muted-note" style={{ marginBottom: 4 }}>Chưa có gói SCORM nào.</p>
      )}
      <input ref={inputRef} type="file" accept=".zip" onChange={handleFile} disabled={uploading} />
      {uploading && <span className="muted-note"> Đang tải lên...</span>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
    </div>
  )
}

function LessonForm({ moduleId, lesson, onSaved, onCancel }) {
  const [title, setTitle] = useState(lesson?.title || '')
  const [type, setType] = useState(lesson?.type || 'text')
  const [contentUrl, setContentUrl] = useState(lesson?.content_url || '')
  const [contentHtml, setContentHtml] = useState(lesson?.content_html || '')
  const [completeRule, setCompleteRule] = useState(lesson?.complete_rule || 'mark')
  const [passWatchPct, setPassWatchPct] = useState(lesson?.pass_watch_pct ?? 80)
  const [antiSeek, setAntiSeek] = useState(lesson?.anti_seek || false)
  const [facePauseWarnSec, setFacePauseWarnSec] = useState(lesson?.face_pause_warn_sec ?? 5)
  const [facePauseStopSec, setFacePauseStopSec] = useState(lesson?.face_pause_stop_sec ?? 10)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function save() {
    if (!title.trim()) {
      setError('Nhập tên bài học.')
      return
    }
    setSaving(true)
    setError('')
    const payload = {
      module: moduleId,
      title: title.trim(),
      type,
      content_url: type !== 'text' && type !== 'scorm' ? contentUrl.trim() : '',
      content_html: type === 'text' ? contentHtml : '',
      // SCORM tu bao hoan thanh qua ScormCommitView (mark_done=True) - complete_rule khong
      // dung den, giu mac dinh 'mark' cho don gian.
      complete_rule: type === 'scorm' ? 'mark' : completeRule,
      pass_watch_pct: Number(passWatchPct) || 80,
      anti_seek: antiSeek,
      face_pause_warn_sec: Number(facePauseWarnSec) || 5,
      face_pause_stop_sec: Number(facePauseStopSec) || 10,
    }
    try {
      if (lesson) {
        await api.patch(`/courses/lessons/${lesson.id}/`, payload)
      } else {
        await api.post('/courses/lessons/', payload)
      }
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không lưu được bài học.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: 8, marginBottom: 8 }}>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Tên bài học"
        style={{ ...s.input, width: '100%', marginBottom: 8 }}
        autoFocus
      />
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={type} onChange={(e) => setType(e.target.value)} style={s.select}>
          {LESSON_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        {type !== 'scorm' && (
          <select value={completeRule} onChange={(e) => setCompleteRule(e.target.value)} style={s.select}>
            {COMPLETE_RULES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        )}
        {completeRule === 'watch_pct' && type !== 'scorm' && (
          <input
            type="number"
            value={passWatchPct}
            onChange={(e) => setPassWatchPct(e.target.value)}
            style={{ ...s.input, width: 100 }}
            placeholder="% xem đủ"
          />
        )}
        {type === 'video_r2' && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
            <input type="checkbox" checked={antiSeek} onChange={(e) => setAntiSeek(e.target.checked)} />
            Chống tua + tự tạm dừng khi mất mặt (webcam)
          </label>
        )}
      </div>
      {type === 'video_r2' && antiSeek && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ fontSize: 13 }}>
            Cảnh báo sau (giây){' '}
            <input
              type="number" value={facePauseWarnSec}
              onChange={(e) => setFacePauseWarnSec(e.target.value)}
              style={{ ...s.input, width: 80 }}
            />
          </label>
          <label style={{ fontSize: 13 }}>
            Tự tạm dừng sau (giây){' '}
            <input
              type="number" value={facePauseStopSec}
              onChange={(e) => setFacePauseStopSec(e.target.value)}
              style={{ ...s.input, width: 80 }}
            />
          </label>
        </div>
      )}
      {type === 'scorm' ? (
        lesson ? (
          <ScormUploadWidget lesson={lesson} onUploaded={() => {}} />
        ) : (
          <p className="muted-note" style={{ marginBottom: 8 }}>
            Lưu bài học trước, sau đó bấm "Sửa" để tải lên gói SCORM (.zip xuất từ Articulate 360).
          </p>
        )
      ) : type === 'text' ? (
        <textarea
          value={contentHtml}
          onChange={(e) => setContentHtml(e.target.value)}
          placeholder="Nội dung bài học..."
          style={{ width: '100%', minHeight: 100, marginBottom: 8 }}
        />
      ) : (
        <input
          value={contentUrl}
          onChange={(e) => setContentUrl(e.target.value)}
          placeholder={type === 'pdf' ? 'URL file PDF...' : 'URL video/liên kết...'}
          style={{ ...s.input, width: '100%', marginBottom: 8 }}
        />
      )}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={save} disabled={saving}>
          Lưu
        </button>
        <button className="btn-outline" onClick={onCancel}>
          Hủy
        </button>
      </div>
    </div>
  )
}

function ModuleBlock({ module, index, onDragHandlers, onChanged }) {
  const [addingLesson, setAddingLesson] = useState(false)
  const [editingLessonId, setEditingLessonId] = useState(null)
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState(module.title)

  const lessons = module.lessons || []
  const lessonDrag = useDragReorder(lessons, (next) => {
    const items = next.map((l, i) => ({ id: l.id, order: i }))
    api.post('/courses/reorder/', { model: 'lesson', items }).then(onChanged)
  })

  async function renameModule() {
    if (!title.trim()) return
    await api.patch(`/courses/modules/${module.id}/`, { title: title.trim() })
    setRenaming(false)
    onChanged()
  }

  async function deleteModule() {
    if (!window.confirm(`Xóa chương "${module.title}" và toàn bộ bài trong chương?`)) return
    await api.delete(`/courses/modules/${module.id}/`)
    onChanged()
  }

  async function deleteLesson(lessonId) {
    if (!window.confirm('Xóa bài học này?')) return
    await api.delete(`/courses/lessons/${lessonId}/`)
    onChanged()
  }

  return (
    <div
      className="card"
      style={{ marginBottom: 12, cursor: 'grab' }}
      draggable
      onDragStart={onDragHandlers.onDragStart(index)}
      onDragOver={onDragHandlers.onDragOver}
      onDrop={onDragHandlers.onDropAt(index)}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span title="Kéo để sắp xếp lại" style={{ cursor: 'grab' }}>
          ⠿
        </span>
        {renaming ? (
          <>
            <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ ...s.input, flex: 1 }} />
            <button className="btn-outline btn-sm" onClick={renameModule}>
              Lưu
            </button>
          </>
        ) : (
          <>
            <strong style={{ flex: 1 }}>{module.title}</strong>
            <button className="btn-outline btn-sm" onClick={() => setRenaming(true)}>
              Sửa tên
            </button>
          </>
        )}
        <button className="btn-outline btn-sm" onClick={deleteModule}>
          Xóa chương
        </button>
      </div>

      {lessons.map((lesson, li) => (
        <div
          key={lesson.id}
          draggable
          onDragStart={lessonDrag.onDragStart(li)}
          onDragOver={lessonDrag.onDragOver}
          onDrop={lessonDrag.onDropAt(li)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
            borderBottom: '1px solid var(--card-border)', cursor: 'grab',
          }}
        >
          <span>⠿</span>
          <span style={{ flex: 1 }}>
            {lesson.title} <span className="muted-note">({LESSON_TYPES.find((t) => t.value === lesson.type)?.label})</span>
          </span>
          <button className="btn-outline btn-sm" onClick={() => setEditingLessonId(lesson.id)}>
            Sửa
          </button>
          <button className="btn-outline btn-sm" onClick={() => deleteLesson(lesson.id)}>
            Xóa
          </button>
        </div>
      ))}
      {lessons.length === 0 && <p className="muted-note">Chưa có bài học nào.</p>}

      {editingLessonId && (
        <LessonForm
          moduleId={module.id}
          lesson={lessons.find((l) => l.id === editingLessonId)}
          onSaved={() => { setEditingLessonId(null); onChanged() }}
          onCancel={() => setEditingLessonId(null)}
        />
      )}

      {addingLesson ? (
        <LessonForm
          moduleId={module.id}
          onSaved={() => { setAddingLesson(false); onChanged() }}
          onCancel={() => setAddingLesson(false)}
        />
      ) : (
        <button className="btn-outline btn-sm" style={{ marginTop: 8 }} onClick={() => setAddingLesson(true)}>
          + Thêm bài học
        </button>
      )}
    </div>
  )
}

function AssignModal({ courseId, open, onClose }) {
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
      const { data } = await api.post(`/courses/${courseId}/assign/`, payload)
      setMessage(`Đã gán cho ${data.created} nhân sự mới.`)
      setSelected([])
    } catch (err) {
      setError(err.response?.data?.detail || 'Không gán được khóa học.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} title="Gán khóa học" onClose={onClose}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button
          className={mode === 'individual' ? '' : 'btn-outline'}
          onClick={() => setMode('individual')}
        >
          Theo cá nhân
        </button>
        <button className={mode === 'filter' ? '' : 'btn-outline'} onClick={() => setMode('filter')}>
          Theo vị trí / nhà hàng
        </button>
      </div>

      {mode === 'individual' ? (
        <>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm nhân sự theo mã / tên..."
            style={{ ...s.input, width: '100%' }}
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
                <span
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelected((prev) => prev.filter((x) => x.id !== e.id))}
                >
                  ✕
                </span>
              </span>
            ))}
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            placeholder="Vị trí (vd Phục vụ) - để trống nếu không lọc"
            style={s.input}
          />
          <select value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)} style={s.select}>
            <option value="">Tất cả nhà hàng</option>
            {restaurantOptions.results.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <input
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            placeholder="Nhóm cấp (level_group, vd S/O/P) - để trống nếu không lọc"
            style={s.input}
          />
        </div>
      )}

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {message && <p style={{ color: 'var(--forest-dark)' }}>{message}</p>}
      <div style={{ marginTop: 12 }}>
        <button onClick={submit} disabled={saving}>
          Gán khóa học
        </button>
      </div>
    </Modal>
  )
}

function OfflineConfirmModal({ course, open, onClose, onDone }) {
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])
  const [employee, setEmployee] = useState(null)
  const [targetType, setTargetType] = useState('course')
  const [lessonId, setLessonId] = useState('')
  const [method, setMethod] = useState('kem_tai_cho')
  const [note, setNote] = useState('')
  const [evidenceUrl, setEvidenceUrl] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const allLessons = (course?.modules || []).flatMap((m) => m.lessons.map((l) => ({ ...l, moduleTitle: m.title })))

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

  async function submit() {
    if (!employee) {
      setError('Chọn nhân sự.')
      return
    }
    if (targetType === 'lesson' && !lessonId) {
      setError('Chọn bài học.')
      return
    }
    setSaving(true)
    setError('')
    setMessage('')
    try {
      await api.post('/courses/offline-confirm/', {
        employee: employee.id, target_type: targetType,
        target_id: targetType === 'course' ? course.id : Number(lessonId),
        method, note, evidence_url: evidenceUrl,
      })
      setMessage(`Đã xác nhận hoàn thành offline cho ${employee.name}.`)
      onDone()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không xác nhận được.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} title="Xác nhận hoàn thành hộ (offline)" onClose={onClose}>
      <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Nhân sự</label>
      <input
        value={employee ? `${employee.code} — ${employee.name}` : search}
        onChange={(e) => { setEmployee(null); setSearch(e.target.value) }}
        placeholder="Tìm theo mã / tên..." style={{ ...s.input, width: '100%', marginBottom: 4 }}
      />
      {results.length > 0 && !employee && (
        <div style={{ border: '1px solid var(--card-border)', borderRadius: 6, marginBottom: 8 }}>
          {results.map((emp) => (
            <div
              key={emp.id} style={{ padding: 8, cursor: 'pointer' }}
              onClick={() => { setEmployee(emp); setResults([]); setSearch('') }}
            >
              {emp.code} — {emp.name} ({emp.position})
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, margin: '8px 0' }}>
        <button className={targetType === 'course' ? '' : 'btn-outline'} onClick={() => setTargetType('course')}>
          Cả khóa học
        </button>
        <button className={targetType === 'lesson' ? '' : 'btn-outline'} onClick={() => setTargetType('lesson')}>
          1 bài học
        </button>
      </div>
      {targetType === 'lesson' && (
        <select value={lessonId} onChange={(e) => setLessonId(e.target.value)} style={{ ...s.select, width: '100%', marginBottom: 8 }}>
          <option value="">— Chọn bài học —</option>
          {allLessons.map((l) => (
            <option key={l.id} value={l.id}>{l.moduleTitle} — {l.title}</option>
          ))}
        </select>
      )}

      <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Hình thức</label>
      <select value={method} onChange={(e) => setMethod(e.target.value)} style={{ ...s.select, width: '100%', marginBottom: 8 }}>
        <option value="kem_tai_cho">Kèm tại chỗ</option>
        <option value="video_nhom">Học nhóm qua video</option>
        <option value="checklist_giay">Checklist giấy</option>
        <option value="khac">Khác</option>
      </select>

      <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Ghi chú (tùy chọn)</label>
      <textarea
        value={note} onChange={(e) => setNote(e.target.value)}
        style={{ width: '100%', minHeight: 50, marginBottom: 8 }}
      />

      <div style={{ marginBottom: 8 }}>
        <PhotoSlot label="Ảnh minh chứng (tùy chọn)" value={evidenceUrl} onChange={setEvidenceUrl} />
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {message && <p style={{ color: 'var(--forest-dark)' }}>{message}</p>}
      <button onClick={submit} disabled={saving}>Xác nhận</button>
    </Modal>
  )
}

export default function CourseEditPage() {
  const { id } = useParams()
  const competencyOptions = useCompetencyOptions()
  const [course, setCourse] = useState(null)
  const [error, setError] = useState('')
  const [addingModule, setAddingModule] = useState(false)
  const [newModuleTitle, setNewModuleTitle] = useState('')
  const [assignOpen, setAssignOpen] = useState(false)
  const [offlineConfirmOpen, setOfflineConfirmOpen] = useState(false)
  const [offlineReport, setOfflineReport] = useState(null)
  const [savingField, setSavingField] = useState(false)

  function loadOfflineReport() {
    api.get(`/courses/${id}/offline-report/`).then(({ data }) => setOfflineReport(data)).catch(() => {})
  }
  useEffect(loadOfflineReport, [id])

  function load() {
    api
      .get(`/courses/${id}/`)
      .then(({ data }) => setCourse(data))
      .catch(() => setError('Không tải được khóa học.'))
  }

  useEffect(load, [id])

  const moduleDrag = useDragReorder(course?.modules || [], (next) => {
    const items = next.map((m, i) => ({ id: m.id, order: i }))
    api.post('/courses/reorder/', { model: 'module', items }).then(load)
  })

  async function updateField(field, value) {
    setSavingField(true)
    try {
      await api.patch(`/courses/${id}/`, { [field]: value })
      load()
    } finally {
      setSavingField(false)
    }
  }

  async function addModule() {
    if (!newModuleTitle.trim()) return
    await api.post('/courses/modules/', {
      course: id, title: newModuleTitle.trim(), order: (course?.modules || []).length,
    })
    setNewModuleTitle('')
    setAddingModule(false)
    load()
  }

  if (error) {
    return (
      <AppShell>
        <p style={{ color: 'var(--danger)' }}>{error}</p>
      </AppShell>
    )
  }
  if (!course) {
    return (
      <AppShell>
        <p className="muted-note">Đang tải...</p>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <Link to="/courses-admin">&larr; Danh sách khóa học</Link>
      <h2 style={{ marginTop: 8 }}>{course.title}</h2>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <PhotoSlot label="Ảnh bìa" value={course.cover_url} onChange={(v) => updateField('cover_url', v)} />
          <div style={{ flex: 1, minWidth: 260 }}>
            <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Tên khóa học</label>
            <input
              defaultValue={course.title}
              onBlur={(e) => e.target.value !== course.title && updateField('title', e.target.value)}
              style={{ ...s.input, width: '100%', marginBottom: 8 }}
            />
            <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Mô tả</label>
            <textarea
              defaultValue={course.description}
              onBlur={(e) => e.target.value !== course.description && updateField('description', e.target.value)}
              style={{ width: '100%', minHeight: 60, marginBottom: 8 }}
            />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <label style={{ fontSize: 13, color: 'var(--muted)' }}>Trạng thái</label>
              <select value={course.status} onChange={(e) => updateField('status', e.target.value)} style={s.select} disabled={savingField}>
                <option value="draft">Nháp</option>
                <option value="published">Xuất bản</option>
                <option value="archived">Lưu trữ</option>
              </select>
              <button onClick={() => setAssignOpen(true)}>Gán khóa học</button>
              <button className="btn-outline" onClick={() => setOfflineConfirmOpen(true)}>
                Xác nhận hoàn thành hộ
              </button>
            </div>
            <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
              Năng lực (dùng để tính điểm Hồ sơ 360)
            </label>
            <CompetencySelect
              value={course.competency}
              onChange={(v) => updateField('competency', v)}
              options={competencyOptions}
              disabled={savingField}
              style={{ width: '100%' }}
            />
            <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
              Mã đồng bộ hồ sơ (sync_course_code) — để trống = không đồng bộ CourseResult
            </label>
            <input
              defaultValue={course.sync_course_code}
              onBlur={(e) => e.target.value !== course.sync_course_code && updateField('sync_course_code', e.target.value)}
              placeholder="vd HOINHAP_PHUCVU..." style={{ ...s.input, width: '100%' }}
            />
            {offlineReport && offlineReport.total_done > 0 && (
              <p className="muted-note" style={{ marginTop: 6 }}>
                Hoàn thành: {offlineReport.total_done} bài — trực tuyến {offlineReport.online} ·
                offline {offlineReport.offline} ({offlineReport.offline_percent}%)
              </p>
            )}
          </div>
        </div>
      </div>

      <h3>Chương &amp; Bài học</h3>
      {(course.modules || []).map((m, i) => (
        <ModuleBlock key={m.id} module={m} index={i} onDragHandlers={moduleDrag} onChanged={load} />
      ))}

      {addingModule ? (
        <div className="card" style={{ display: 'flex', gap: 8 }}>
          <input
            value={newModuleTitle}
            onChange={(e) => setNewModuleTitle(e.target.value)}
            placeholder="Tên chương..."
            style={{ ...s.input, flex: 1 }}
            autoFocus
          />
          <button onClick={addModule}>Lưu</button>
          <button className="btn-outline" onClick={() => setAddingModule(false)}>
            Hủy
          </button>
        </div>
      ) : (
        <button className="btn-outline" onClick={() => setAddingModule(true)}>
          + Thêm chương
        </button>
      )}

      <AssignModal courseId={id} open={assignOpen} onClose={() => setAssignOpen(false)} />
      <OfflineConfirmModal
        course={course} open={offlineConfirmOpen} onClose={() => setOfflineConfirmOpen(false)}
        onDone={() => { load(); loadOfflineReport() }}
      />
    </AppShell>
  )
}
