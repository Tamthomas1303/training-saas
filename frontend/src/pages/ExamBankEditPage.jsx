import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import api from '../api/client'
import { DIFFICULTIES, QUESTION_TYPES, typeLabel } from '../config/examQuestionTypes'
import * as s from './listPageStyles'

// Xuat/Nhap Excel gan nang luc hang loat cho cau hoi (Prompt_GanNangLuc_CauHoi_Excel.md) - nut
// tren man Ngan hang cau hoi, dung dung bo loc dang chon (bank/dang/cap do/tim kiem).
function ImportCompetencyModal({ open, onClose, onDone }) {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function reset() {
    setFile(null); setPreview(null); setError('')
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleFile(e) {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setError('')
    setBusy(true)
    const formData = new FormData()
    formData.append('file', f)
    formData.append('dry_run', 'true')
    try {
      const { data } = await api.post('/exams/questions/import-competency/', formData)
      setPreview(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không đọc được file.')
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    if (!file) return
    setBusy(true)
    setError('')
    const formData = new FormData()
    formData.append('file', file)
    formData.append('dry_run', 'false')
    try {
      const { data } = await api.post('/exams/questions/import-competency/', formData)
      onDone(data)
      reset()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không gán được năng lực.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} title="Nhập Excel gán năng lực" onClose={() => { reset(); onClose() }}>
      <p className="muted-note" style={{ marginTop: 0 }}>
        Chọn file đã điền cột NĂNG LỰC (chọn) — hệ thống sẽ xem trước trước khi ghi thật.
      </p>
      <input ref={inputRef} type="file" accept=".xlsx" onChange={handleFile} disabled={busy} />
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {preview && (
        <div style={{ marginTop: 12 }}>
          <p>
            Sẽ gán năng lực cho <strong>{preview.stats.will_assign}</strong> câu · giữ nguyên{' '}
            <strong>{preview.stats.unchanged_blank}</strong> câu (để trống) · lỗi{' '}
            <strong>{preview.stats.errors}</strong> dòng.
          </p>
          {preview.errors.length > 0 && (
            <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: 6, padding: 8 }}>
              {preview.errors.map((e, i) => (
                <div key={i} className="muted-note" style={{ fontSize: 12 }}>Dòng {e.row}: {e.reason}</div>
              ))}
            </div>
          )}
          <button onClick={confirm} disabled={busy || preview.stats.will_assign === 0} style={{ marginTop: 8 }}>
            Xác nhận gán {preview.stats.will_assign} câu
          </button>
        </div>
      )}
    </Modal>
  )
}

const CHOICE_TYPES = ['single', 'multiple', 'truefalse']

function emptyOptions(type) {
  if (type === 'truefalse') {
    return [
      { content_html: 'Đúng', is_correct: true },
      { content_html: 'Sai', is_correct: false },
    ]
  }
  return [{ content_html: '', is_correct: false }, { content_html: '', is_correct: false }]
}

function configToFormFields(type, config) {
  config = config || {}
  if (type === 'text_fill') {
    return { accepted: (config.accepted || []).join(', '), caseSensitive: !!config.case_sensitive }
  }
  if (type === 'numeric') {
    return { answer: config.answer ?? '', tolerance: config.tolerance ?? 0 }
  }
  if (type === 'essay') {
    return { rubric: config.rubric || '' }
  }
  if (type === 'matching') {
    return { pairs: config.pairs?.length ? config.pairs : [{ left: '', right: '' }, { left: '', right: '' }] }
  }
  if (type === 'dragdrop') {
    return {
      tokens: (config.tokens || []).join(', '),
      gaps: config.gaps?.length ? config.gaps : [{ id: 1, answer: '' }, { id: 2, answer: '' }],
    }
  }
  return {}
}

function buildConfig(type, fields) {
  if (type === 'text_fill') {
    return {
      accepted: fields.accepted.split(',').map((s) => s.trim()).filter(Boolean),
      case_sensitive: fields.caseSensitive,
    }
  }
  if (type === 'numeric') {
    return { answer: Number(fields.answer), tolerance: Number(fields.tolerance) || 0 }
  }
  if (type === 'essay') {
    return { rubric: fields.rubric }
  }
  if (type === 'matching') {
    return { pairs: fields.pairs.filter((p) => p.left.trim() && p.right.trim()) }
  }
  if (type === 'dragdrop') {
    return {
      tokens: fields.tokens.split(',').map((s) => s.trim()).filter(Boolean),
      gaps: fields.gaps.filter((g) => String(g.answer).trim()).map((g) => ({ id: g.id, answer: g.answer })),
    }
  }
  return {}
}

function QuestionForm({ bankId, question, onSaved, onCancel }) {
  const [type, setType] = useState(question?.type || 'single')
  const [stemHtml, setStemHtml] = useState(question?.stem_html || '')
  const [points, setPoints] = useState(question?.points ?? 1)
  const [difficulty, setDifficulty] = useState(question?.difficulty || 'medium')
  const [explanationHtml, setExplanationHtml] = useState(question?.explanation_html || '')
  const [mediaUrl, setMediaUrl] = useState(question?.media_url || '')
  const [options, setOptions] = useState(question?.options?.length ? question.options : emptyOptions(type))
  const [fields, setFields] = useState(configToFormFields(type, question?.config))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function changeType(nextType) {
    setType(nextType)
    if (CHOICE_TYPES.includes(nextType)) setOptions(emptyOptions(nextType))
    setFields(configToFormFields(nextType, {}))
  }

  function updateOption(i, patch) {
    setOptions((prev) => prev.map((o, idx) => (idx === i ? { ...o, ...patch } : o)))
  }

  function setSingleCorrect(i) {
    setOptions((prev) => prev.map((o, idx) => ({ ...o, is_correct: idx === i })))
  }

  async function save() {
    if (!stemHtml.trim()) {
      setError('Nhập nội dung câu hỏi.')
      return
    }
    setSaving(true)
    setError('')
    const payload = {
      bank: bankId, type, stem_html: stemHtml.trim(), points: Number(points) || 1, difficulty,
      explanation_html: explanationHtml, media_url: mediaUrl.trim(),
      config: buildConfig(type, fields),
    }
    if (CHOICE_TYPES.includes(type)) {
      payload.options = options.filter((o) => o.content_html.trim() !== '' || type === 'truefalse')
    }
    try {
      if (question) {
        await api.patch(`/exams/questions/${question.id}/`, payload)
      } else {
        await api.post('/exams/questions/', payload)
      }
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không lưu được câu hỏi.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: 8, marginBottom: 8 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <select value={type} onChange={(e) => changeType(e.target.value)} style={s.select} disabled={!!question}>
          {QUESTION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} style={s.select}>
          {DIFFICULTIES.map((d) => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>
        <input
          type="number" value={points} onChange={(e) => setPoints(e.target.value)}
          placeholder="Điểm" style={{ ...s.input, width: 90 }}
        />
      </div>

      <textarea
        value={stemHtml}
        onChange={(e) => setStemHtml(e.target.value)}
        placeholder="Nội dung câu hỏi..."
        style={{ width: '100%', minHeight: 70, marginBottom: 8 }}
        autoFocus
      />
      <input
        value={mediaUrl} onChange={(e) => setMediaUrl(e.target.value)}
        placeholder="URL ảnh/video minh họa (tùy chọn)" style={{ ...s.input, width: '100%', marginBottom: 8 }}
      />

      {CHOICE_TYPES.includes(type) && (
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
            Đáp án {type === 'multiple' ? '(chọn nhiều đáp án đúng)' : '(chọn 1 đáp án đúng)'}
          </label>
          {options.map((opt, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
              {type === 'multiple' ? (
                <input
                  type="checkbox" checked={opt.is_correct}
                  onChange={(e) => updateOption(i, { is_correct: e.target.checked })}
                />
              ) : (
                <input
                  type="radio" name="single-correct" checked={opt.is_correct}
                  onChange={() => setSingleCorrect(i)} disabled={type === 'truefalse'}
                />
              )}
              <input
                value={opt.content_html}
                onChange={(e) => updateOption(i, { content_html: e.target.value })}
                placeholder={`Đáp án ${i + 1}`} style={{ ...s.input, flex: 1 }}
                disabled={type === 'truefalse'}
              />
              {type !== 'truefalse' && options.length > 2 && (
                <button
                  className="btn-outline btn-sm"
                  onClick={() => setOptions((prev) => prev.filter((_, idx) => idx !== i))}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          {type !== 'truefalse' && (
            <button
              className="btn-outline btn-sm"
              onClick={() => setOptions((prev) => [...prev, { content_html: '', is_correct: false }])}
            >
              + Thêm đáp án
            </button>
          )}
        </div>
      )}

      {type === 'text_fill' && (
        <div style={{ marginBottom: 8 }}>
          <input
            value={fields.accepted}
            onChange={(e) => setFields((f) => ({ ...f, accepted: e.target.value }))}
            placeholder="Đáp án chấp nhận, cách nhau bởi dấu phẩy" style={{ ...s.input, width: '100%', marginBottom: 4 }}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
            <input
              type="checkbox" checked={fields.caseSensitive}
              onChange={(e) => setFields((f) => ({ ...f, caseSensitive: e.target.checked }))}
            /> Phân biệt hoa/thường
          </label>
        </div>
      )}

      {type === 'numeric' && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <input
            type="number" value={fields.answer}
            onChange={(e) => setFields((f) => ({ ...f, answer: e.target.value }))}
            placeholder="Đáp án số" style={s.input}
          />
          <input
            type="number" value={fields.tolerance}
            onChange={(e) => setFields((f) => ({ ...f, tolerance: e.target.value }))}
            placeholder="Sai số cho phép" style={s.input}
          />
        </div>
      )}

      {type === 'essay' && (
        <textarea
          value={fields.rubric}
          onChange={(e) => setFields((f) => ({ ...f, rubric: e.target.value }))}
          placeholder="Gợi ý chấm điểm (tùy chọn, chỉ người chấm tay thấy)"
          style={{ width: '100%', minHeight: 50, marginBottom: 8 }}
        />
      )}

      {type === 'matching' && (
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
            Các cặp nối đúng
          </label>
          {fields.pairs.map((p, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
              <input
                value={p.left}
                onChange={(e) => setFields((f) => ({
                  ...f, pairs: f.pairs.map((x, idx) => (idx === i ? { ...x, left: e.target.value } : x)),
                }))}
                placeholder="Vế trái" style={{ ...s.input, flex: 1 }}
              />
              <span>—</span>
              <input
                value={p.right}
                onChange={(e) => setFields((f) => ({
                  ...f, pairs: f.pairs.map((x, idx) => (idx === i ? { ...x, right: e.target.value } : x)),
                }))}
                placeholder="Vế phải" style={{ ...s.input, flex: 1 }}
              />
              {fields.pairs.length > 2 && (
                <button
                  className="btn-outline btn-sm"
                  onClick={() => setFields((f) => ({ ...f, pairs: f.pairs.filter((_, idx) => idx !== i) }))}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <button
            className="btn-outline btn-sm"
            onClick={() => setFields((f) => ({ ...f, pairs: [...f.pairs, { left: '', right: '' }] }))}
          >
            + Thêm cặp
          </button>
        </div>
      )}

      {type === 'dragdrop' && (
        <div style={{ marginBottom: 8 }}>
          <input
            value={fields.tokens}
            onChange={(e) => setFields((f) => ({ ...f, tokens: e.target.value }))}
            placeholder="Danh sách từ để kéo-thả, cách nhau bởi dấu phẩy" style={{ ...s.input, width: '100%', marginBottom: 4 }}
          />
          <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
            Chỗ trống — số thứ tự &amp; đáp án đúng (phải là 1 trong các từ ở trên)
          </label>
          {fields.gaps.map((g, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4, alignItems: 'center' }}>
              <span className="muted-note">Chỗ trống #{g.id}</span>
              <input
                value={g.answer}
                onChange={(e) => setFields((f) => ({
                  ...f, gaps: f.gaps.map((x, idx) => (idx === i ? { ...x, answer: e.target.value } : x)),
                }))}
                placeholder="Đáp án đúng" style={{ ...s.input, flex: 1 }}
              />
              {fields.gaps.length > 1 && (
                <button
                  className="btn-outline btn-sm"
                  onClick={() => setFields((f) => ({ ...f, gaps: f.gaps.filter((_, idx) => idx !== i) }))}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <button
            className="btn-outline btn-sm"
            onClick={() => setFields((f) => ({
              ...f, gaps: [...f.gaps, { id: (f.gaps.at(-1)?.id || 0) + 1, answer: '' }],
            }))}
          >
            + Thêm chỗ trống
          </button>
        </div>
      )}

      <textarea
        value={explanationHtml}
        onChange={(e) => setExplanationHtml(e.target.value)}
        placeholder="Giải thích đáp án (hiện cho học viên sau khi nộp bài, tùy chọn)"
        style={{ width: '100%', minHeight: 50, marginBottom: 8 }}
      />

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={save} disabled={saving}>Lưu</button>
        <button className="btn-outline" onClick={onCancel}>Hủy</button>
      </div>
    </div>
  )
}

export default function ExamBankEditPage() {
  const { id } = useParams()
  const [bank, setBank] = useState(null)
  const [questions, setQuestions] = useState([])
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [difficultyFilter, setDifficultyFilter] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [importResult, setImportResult] = useState(null)

  function load() {
    Promise.all([
      api.get(`/exams/banks/${id}/`),
      api.get('/exams/questions/', {
        params: {
          bank: id, page_size: 200, search: search || undefined,
          type: typeFilter || undefined, difficulty: difficultyFilter || undefined,
        },
      }),
    ])
      .then(([bankRes, questionsRes]) => {
        setBank(bankRes.data)
        setQuestions(questionsRes.data.results)
      })
      .catch(() => setError('Không tải được ngân hàng câu hỏi.'))
  }

  useEffect(load, [id, search, typeFilter, difficultyFilter])

  async function deleteQuestion(qid) {
    if (!window.confirm('Xóa câu hỏi này?')) return
    await api.delete(`/exams/questions/${qid}/`)
    load()
  }

  async function exportCompetencyExcel() {
    const resp = await api.get('/exams/questions/export-competency/', {
      params: {
        bank: id, search: search || undefined, type: typeFilter || undefined,
        difficulty: difficultyFilter || undefined,
      },
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'gan_nang_luc_cau_hoi.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  if (error) {
    return <AppShell><p style={{ color: 'var(--danger)' }}>{error}</p></AppShell>
  }
  if (!bank) {
    return <AppShell><p className="muted-note">Đang tải...</p></AppShell>
  }

  return (
    <AppShell>
      <Link to="/exam-banks">&larr; Ngân hàng câu hỏi</Link>
      <h2 style={{ marginTop: 8 }}>{bank.name}</h2>

      <FilterBar>
        <input
          value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm nội dung câu hỏi..." style={{ ...s.input, minWidth: 220 }}
        />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={s.select}>
          <option value="">Mọi dạng câu hỏi</option>
          {QUESTION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select value={difficultyFilter} onChange={(e) => setDifficultyFilter(e.target.value)} style={s.select}>
          <option value="">Mọi cấp độ</option>
          {DIFFICULTIES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <button className="btn-outline btn-sm" onClick={exportCompetencyExcel}>Xuất Excel gán năng lực</button>
        <button className="btn-outline btn-sm" onClick={() => setImportOpen(true)}>Nhập Excel gán năng lực</button>
      </FilterBar>

      {importResult && (
        <p className="muted-note">
          Đã gán năng lực cho {importResult.stats.will_assign} câu
          {importResult.stats.errors > 0 ? ` · ${importResult.stats.errors} dòng lỗi` : ''}.
        </p>
      )}

      {questions.map((q) => (
        editingId === q.id ? (
          <QuestionForm
            key={q.id} bankId={id} question={q}
            onSaved={() => { setEditingId(null); load() }}
            onCancel={() => setEditingId(null)}
          />
        ) : (
          <div key={q.id} className="card" style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="badge badge-neutral">{typeLabel(q.type)}</span>
            <span style={{ flex: 1 }}>{q.stem_html}</span>
            {q.competency_name ? (
              <Badge variant="success">{q.competency_name}</Badge>
            ) : (
              <span className="muted-note" style={{ fontSize: 12 }}>Chưa gán năng lực</span>
            )}
            <span className="muted-note">{q.points} điểm</span>
            <button className="btn-outline btn-sm" onClick={() => setEditingId(q.id)}>Sửa</button>
            <button className="btn-outline btn-sm" onClick={() => deleteQuestion(q.id)}>Xóa</button>
          </div>
        )
      ))}
      {questions.length === 0 && !adding && <p className="muted-note">Chưa có câu hỏi nào.</p>}

      <ImportCompetencyModal
        open={importOpen} onClose={() => setImportOpen(false)}
        onDone={(data) => { setImportResult(data); load() }}
      />

      {adding ? (
        <QuestionForm bankId={id} onSaved={() => { setAdding(false); load() }} onCancel={() => setAdding(false)} />
      ) : (
        <button className="btn-outline" onClick={() => setAdding(true)}>+ Thêm câu hỏi</button>
      )}
    </AppShell>
  )
}
