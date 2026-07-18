import { useRef, useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import CouncilForm from '../components/CouncilForm'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import ProgressBar from '../components/ProgressBar'
import SignaturePad from '../components/SignaturePad'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import { submitGuarded } from '../utils/offlineQueue'
import { compressImageFile } from '../utils/compressImage'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const EVAL_TYPE_OPTIONS = [
  { value: 'Skill_BQL', label: 'BQL đánh giá kỹ năng' },
  { value: 'AM_KCS', label: 'AM/KCS kiểm tra random' },
]

// Phân vai (khớp backend evaluation/services.py): mỗi vai trò chỉ thấy loại đánh giá của mình.
const ALLOWED_EVAL_TYPES_BY_ROLE = {
  bql: ['Skill_BQL'],
  am: ['AM_KCS'],
  kcs: ['AM_KCS'],
  admin: ['Skill_BQL', 'AM_KCS'],
  om: ['Skill_BQL', 'AM_KCS'],
}

function clamp(value, min, max) {
  if (Number.isNaN(value)) return min
  return Math.min(max, Math.max(min, value))
}

function EvalPhotoButton({ value, onChange }) {
  const inputRef = useRef(null)

  async function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    const dataUrl = await compressImageFile(file)
    onChange(dataUrl)
  }

  return (
    <div style={{ textAlign: 'center' }}>
      <div
        onClick={() => inputRef.current?.click()}
        style={{
          width: 48,
          height: 38,
          border: '1px dashed var(--card-border)',
          borderRadius: 6,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          background: 'var(--page-bg)',
          margin: '0 auto',
        }}
      >
        {value ? (
          <img src={value} alt="minh chứng" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ fontSize: 16 }}>📷</span>
        )}
      </div>
      <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFile} />
    </div>
  )
}

export default function EvaluationPage() {
  const { user } = useAuth()
  const role = (user?.role || '').toLowerCase()
  const allowedTypes = ALLOWED_EVAL_TYPES_BY_ROLE[role] || ['Skill_BQL']
  const evalTypeOptions = EVAL_TYPE_OPTIONS.filter((o) => allowedTypes.includes(o.value))
  const canCouncil = !['bql', 'trainer'].includes(role)

  const [employeeSearch, setEmployeeSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [evalType, setEvalType] = useState(allowedTypes[0] || 'Skill_BQL')

  const [criteriaData, setCriteriaData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  const [scores, setScores] = useState({})
  const [photos, setPhotos] = useState({})
  const [notes, setNotes] = useState({})
  const [generalNote, setGeneralNote] = useState('')
  const [signEvaluator, setSignEvaluator] = useState('')
  const [signTrainee, setSignTrainee] = useState('')
  const [existingSignEvaluator, setExistingSignEvaluator] = useState('')
  const [existingSignTrainee, setExistingSignTrainee] = useState('')

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saveMessage, setSaveMessage] = useState('')
  const [pdfUrl, setPdfUrl] = useState('')
  const [showCouncil, setShowCouncil] = useState(false)

  const { data: employeeOptions } = usePaginatedList('/employees/', {
    search: employeeSearch,
    page,
    page_size: PAGE_SIZE,
  })

  function resetForm() {
    setScores({})
    setPhotos({})
    setNotes({})
    setGeneralNote('')
    setSignEvaluator('')
    setSignTrainee('')
    setExistingSignEvaluator('')
    setExistingSignTrainee('')
    setSaveError('')
    setSaveMessage('')
    setPdfUrl('')
  }

  async function loadEvaluation(employeeId, type) {
    setLoading(true)
    setLoadError('')
    resetForm()
    try {
      const [criteriaResp, draftResp] = await Promise.all([
        api.get('/evaluation/criteria/', { params: { employee: employeeId, eval_type: type } }),
        api.get('/evaluation/draft/', { params: { employee: employeeId, eval_type: type } }),
      ])
      setCriteriaData(criteriaResp.data)

      const draft = draftResp.data.draft
      if (draft) {
        const scoreMap = {}
        const photoMap = {}
        const noteMap = {}
        draft.details.forEach((d) => {
          scoreMap[d.criteria_id] = Number(d.score)
          photoMap[d.criteria_id] = d.photo_url
          noteMap[d.criteria_id] = d.note
        })
        setScores(scoreMap)
        setPhotos(photoMap)
        setNotes(noteMap)
        setGeneralNote(draft.note || '')
        setExistingSignEvaluator(draft.sign_evaluator || '')
        setExistingSignTrainee(draft.sign_trainee || '')
      }
    } catch {
      setLoadError('Không tải được dữ liệu đánh giá.')
    } finally {
      setLoading(false)
    }
  }

  function selectEmployee(emp) {
    setSelectedEmployee(emp)
    setShowCouncil(false)
    loadEvaluation(emp.id, evalType)
  }

  function changeEvalType(type) {
    setEvalType(type)
    if (selectedEmployee) loadEvaluation(selectedEmployee.id, type)
  }

  function backToPicker() {
    setSelectedEmployee(null)
    setCriteriaData(null)
  }

  const items = criteriaData?.items || []
  const total = items.reduce((sum, c) => sum + (scores[c.criteria_id] ?? 0), 0)
  const maxTotal = items.reduce((sum, c) => sum + c.max_score, 0)
  const percent = maxTotal ? Math.round((total / maxTotal) * 100) : 0
  const mandatoryFail = items.some((c) => c.is_mandatory && (scores[c.criteria_id] ?? 0) <= 0)
  const pass = percent >= 70 && !mandatoryFail

  async function submit(complete) {
    setSaving(true)
    setSaveError('')
    setSaveMessage('')
    const payload = {
      employee: selectedEmployee.id,
      eval_type: evalType,
      details: items.map((c) => ({
        criteria_id: c.criteria_id,
        score: scores[c.criteria_id] ?? 0,
        photo: photos[c.criteria_id] || undefined,
        note: notes[c.criteria_id] || '',
      })),
      note: generalNote,
      sign_evaluator: signEvaluator || existingSignEvaluator,
      sign_trainee: signTrainee || existingSignTrainee,
      complete,
    }
    await submitGuarded(
      'evaluation',
      (p) => api.post('/evaluation/save/', p).then((r) => r.data),
      payload,
      {
        onOk: (data) => {
          setSaveMessage(`Đã lưu (${data.status === 'done' ? 'Hoàn thành' : 'Nháp'}).`)
          setPdfUrl(data.pdf_url || '')
        },
        onErr: setSaveError,
        onQueued: () => setSaveMessage('Mất mạng - đã lưu nháp offline, sẽ tự đồng bộ khi có mạng.'),
      }
    )
    setSaving(false)
  }

  return (
    <AppShell>
      <h2>Đánh giá kỹ năng</h2>

      {!selectedEmployee && (
        <>
          <FilterBar>
            <input
              style={s.input}
              placeholder="Tìm nhân sự theo mã / tên để đánh giá..."
              value={employeeSearch}
              onChange={(e) => {
                setEmployeeSearch(e.target.value)
                setPage(1)
              }}
            />
          </FilterBar>
          <Table>
            <thead>
              <tr>
                <th>Mã NV</th>
                <th>Họ tên</th>
                <th>Nhà hàng</th>
                <th>Vị trí</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {employeeOptions.results.map((emp) => (
                <tr key={emp.id}>
                  <td>{emp.code}</td>
                  <td>{emp.name}</td>
                  <td>{emp.restaurant_name}</td>
                  <td>{emp.position}</td>
                  <td>
                    <button className="btn-outline btn-sm" onClick={() => selectEmployee(emp)}>
                      Chọn
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pager page={page} pageSize={PAGE_SIZE} count={employeeOptions.count} onChange={setPage} />
        </>
      )}

      {selectedEmployee && (
        <>
          <p>
            <button className="btn-outline btn-sm" onClick={backToPicker}>
              « Chọn nhân sự khác
            </button>
          </p>
          <h3>
            {selectedEmployee.name} — {selectedEmployee.position} — {selectedEmployee.restaurant_name}
          </h3>

          {evalTypeOptions.length > 1 ? (
            <FilterBar>
              {evalTypeOptions.map((opt) => (
                <button
                  key={opt.value}
                  className={evalType === opt.value ? '' : 'btn-outline'}
                  onClick={() => changeEvalType(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </FilterBar>
          ) : (
            <p className="muted-note" style={{ fontSize: 13 }}>
              Loại đánh giá: {evalTypeOptions[0]?.label}
            </p>
          )}

          {loading && <p className="muted-note">Đang tải...</p>}
          {loadError && <p style={{ color: 'var(--danger)' }}>{loadError}</p>}

          {criteriaData && !loading && (
            <>
              {criteriaData.source === 'fallback_checklist' && (
                <p style={{ color: 'var(--amber)', fontSize: 13 }}>
                  * Tiêu chí tạm suy từ checklist (chưa nhập bộ tiêu chí đánh giá riêng).
                </p>
              )}
              <p className="muted-note" style={{ fontSize: 13 }}>
                Tiến độ đào tạo: {criteriaData.training_progress_percent}%
                {evalType === 'AM_KCS' && (
                  <> · Đã qua BQL đánh giá: {criteriaData.has_bql_evaluation ? 'Có' : 'Chưa'}</>
                )}
              </p>

              {evalType === 'AM_KCS' && !criteriaData.has_bql_evaluation ? (
                <p style={{ color: 'var(--danger)' }}>
                  Nhân sự này chưa được BQL đánh giá kỹ năng, chưa thể kiểm tra random.
                </p>
              ) : (
                <>
                  <Table>
                    <thead>
                      <tr>
                        <th>Nội dung</th>
                        <th>Điểm tối đa</th>
                        <th>Chấm điểm</th>
                        <th>Ảnh KN</th>
                        <th>Ghi chú</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((c) => (
                        <tr key={c.criteria_id}>
                          <td>
                            {c.content}
                            {c.is_mandatory && (
                              <span style={{ marginLeft: 6 }}>
                                <Badge variant="danger">Bắt buộc</Badge>
                              </span>
                            )}
                          </td>
                          <td style={{ textAlign: 'center' }}>{c.max_score}</td>
                          <td style={{ textAlign: 'center' }}>
                            <input
                              type="number"
                              min="0"
                              max={c.max_score}
                              value={scores[c.criteria_id] ?? 0}
                              onChange={(e) =>
                                setScores((sc) => ({
                                  ...sc,
                                  [c.criteria_id]: clamp(Number(e.target.value), 0, c.max_score),
                                }))
                              }
                              style={{ width: 70 }}
                            />
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <EvalPhotoButton
                              value={photos[c.criteria_id]}
                              onChange={(v) => setPhotos((p) => ({ ...p, [c.criteria_id]: v }))}
                            />
                            {c.require_photo && (
                              <div style={{ fontSize: 10, color: 'var(--danger)' }}>Bắt buộc</div>
                            )}
                          </td>
                          <td>
                            <input
                              type="text"
                              value={notes[c.criteria_id] || ''}
                              onChange={(e) => setNotes((n) => ({ ...n, [c.criteria_id]: e.target.value }))}
                              style={{ width: '100%' }}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>

                  <div style={{ margin: '16px 0' }}>
                    <div
                      style={{
                        display: 'flex',
                        gap: 16,
                        alignItems: 'center',
                        marginBottom: 6,
                        fontWeight: 'bold',
                      }}
                    >
                      <span>
                        Tổng: {total}/{maxTotal}
                      </span>
                      <Badge variant={pass ? 'success' : 'danger'}>
                        {pass ? 'Đạt' : 'Không đạt'} ({percent}%)
                      </Badge>
                    </div>
                    <ProgressBar percent={percent} />
                  </div>

                  <textarea
                    placeholder="Ghi chú chung..."
                    value={generalNote}
                    onChange={(e) => setGeneralNote(e.target.value)}
                    style={{ width: '100%', minHeight: 60, marginBottom: 12 }}
                  />

                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
                    <SignaturePad
                      label="Người đánh giá ký"
                      existingUrl={existingSignEvaluator}
                      value={signEvaluator}
                      onChange={setSignEvaluator}
                    />
                    <SignaturePad
                      label="Nhân viên ký"
                      existingUrl={existingSignTrainee}
                      value={signTrainee}
                      onChange={setSignTrainee}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn-outline" disabled={saving} onClick={() => submit(false)}>
                      Lưu nháp
                    </button>
                    <button disabled={saving} onClick={() => submit(true)}>
                      Hoàn thành & xuất PDF
                    </button>
                  </div>

                  {saving && <p className="muted-note">Đang lưu...</p>}
                  {saveError && <p style={{ color: 'var(--danger)' }}>{saveError}</p>}
                  {saveMessage && (
                    <p style={{ color: 'var(--forest-dark)' }}>
                      {saveMessage}{' '}
                      {pdfUrl && (
                        <a href={pdfUrl} target="_blank" rel="noreferrer">
                          Xem phiếu đánh giá PDF
                        </a>
                      )}
                    </p>
                  )}
                </>
              )}

              {canCouncil && (
                <>
                  <p>
                    <button className="btn-outline btn-sm" onClick={() => setShowCouncil((v) => !v)}>
                      {showCouncil ? 'Ẩn' : 'Hiện'} Chấm điểm hội đồng
                    </button>
                  </p>
                  {showCouncil && <CouncilForm employeeId={selectedEmployee.id} />}
                </>
              )}
            </>
          )}
        </>
      )}
    </AppShell>
  )
}
