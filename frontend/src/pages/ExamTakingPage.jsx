import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import api from '../api/client'
import * as s from './listPageStyles'

function formatCountdown(sec) {
  if (sec <= 0) return '00:00'
  const m = Math.floor(sec / 60)
  const s2 = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s2).padStart(2, '0')}`
}

// Cau hoi single/multiple/truefalse/text_fill/numeric/essay dung 1 dap an don gian; matching
// dung dropdown ghep vao ve trai; dragdrop dung "cham de chon" (tap token roi tap cho trong) -
// mobile-first thay vi HTML5 drag (drag-and-drop khong hoat dong tot tren cam ung khong co thu
// vien rieng), giu tinh than "keo-tha" nhung van dung tren dien thoai.
function QuestionCard({ index, question, response, onChange }) {
  const r = response || {}

  function set(patch) {
    onChange({ ...r, ...patch })
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <strong>Câu {index + 1}</strong>
        <span className="muted-note">({question.points} điểm)</span>
      </div>
      {/* eslint-disable-next-line react/no-danger */}
      <div dangerouslySetInnerHTML={{ __html: question.stem_html }} style={{ marginBottom: 12 }} />
      {question.media_url && (
        <img src={question.media_url} alt="" style={{ maxWidth: '100%', marginBottom: 12, borderRadius: 8 }} />
      )}

      {question.type === 'single' || question.type === 'truefalse' ? (
        <div>
          {question.options.map((opt) => (
            <label key={opt.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0' }}>
              <input
                type="radio" name={`q-${question.id}`} checked={r.option_id === opt.id}
                onChange={() => set({ option_id: opt.id })}
              />
              {opt.content_html}
            </label>
          ))}
        </div>
      ) : question.type === 'multiple' ? (
        <div>
          {question.options.map((opt) => {
            const ids = r.option_ids || []
            return (
              <label key={opt.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0' }}>
                <input
                  type="checkbox" checked={ids.includes(opt.id)}
                  onChange={(e) => set({
                    option_ids: e.target.checked ? [...ids, opt.id] : ids.filter((x) => x !== opt.id),
                  })}
                />
                {opt.content_html}
              </label>
            )
          })}
        </div>
      ) : question.type === 'text_fill' ? (
        <input
          defaultValue={r.text || ''} onBlur={(e) => set({ text: e.target.value })}
          placeholder="Nhập câu trả lời..." style={{ ...s.input, width: '100%' }}
        />
      ) : question.type === 'numeric' ? (
        <input
          type="number" defaultValue={r.value ?? ''} onBlur={(e) => set({ value: Number(e.target.value) })}
          placeholder="Nhập số..." style={{ ...s.input, width: 200 }}
        />
      ) : question.type === 'essay' ? (
        <textarea
          defaultValue={r.text || ''} onBlur={(e) => set({ text: e.target.value })}
          placeholder="Nhập bài làm..." style={{ width: '100%', minHeight: 120 }}
        />
      ) : question.type === 'matching' ? (
        <div>
          {question.left_items.map((left, li) => {
            const pairs = r.pairs || []
            const current = pairs.find((p) => p.left === left)?.right || ''
            return (
              <div key={li} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0' }}>
                <span style={{ minWidth: 140 }}>{left}</span>
                <span>→</span>
                <select
                  value={current} style={s.select}
                  onChange={(e) => {
                    const next = pairs.filter((p) => p.left !== left)
                    if (e.target.value) next.push({ left, right: e.target.value })
                    set({ pairs: next })
                  }}
                >
                  <option value="">— chọn —</option>
                  {question.right_items.map((right, ri) => (
                    <option key={ri} value={right}>{right}</option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
      ) : question.type === 'dragdrop' ? (
        <DragDropQuestion question={question} response={r} onChange={set} />
      ) : null}
    </div>
  )
}

function DragDropQuestion({ question, response, onChange }) {
  const [armed, setArmed] = useState(null)
  const placements = response.placements || {}
  const usedTokens = new Set(Object.values(placements))

  function placeAt(gapId) {
    if (!armed) return
    const next = { ...placements, [gapId]: armed }
    onChange({ placements: next })
    setArmed(null)
  }

  function clearGap(gapId) {
    const next = { ...placements }
    delete next[gapId]
    onChange({ placements: next })
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {question.tokens.map((tok, i) => (
          <button
            key={i} type="button"
            className={armed === tok ? '' : 'btn-outline'}
            disabled={usedTokens.has(tok)}
            onClick={() => setArmed(armed === tok ? null : tok)}
          >
            {tok}
          </button>
        ))}
      </div>
      <p className="muted-note" style={{ marginBottom: 8 }}>
        Chạm chọn 1 từ ở trên rồi chạm vào chỗ trống để điền (giống kéo-thả, dùng được trên điện thoại).
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {question.gaps.map((gap) => (
          <div
            key={gap.id} onClick={() => (placements[gap.id] ? clearGap(gap.id) : placeAt(gap.id))}
            className="card"
            style={{
              minWidth: 80, textAlign: 'center', cursor: 'pointer', padding: '8px 12px',
              background: placements[gap.id] ? 'var(--mint)' : 'transparent',
            }}
          >
            <div className="muted-note" style={{ fontSize: 11 }}>Chỗ trống #{gap.id}</div>
            <div>{placements[gap.id] || '...'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ResultView({ result }) {
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Kết quả</h3>
      {result.status === 'submitted' ? (
        <p>Bài thi có câu tự luận, đang chờ chấm tay. Kết quả sẽ hiện sau khi được chấm.</p>
      ) : (
        <>
          <p>
            Điểm: <strong>{result.score}/{result.max_score}</strong> ({result.percent}%) —{' '}
            <strong style={{ color: result.passed ? 'var(--forest-dark)' : 'var(--danger)' }}>
              {result.passed ? 'ĐẠT' : 'CHƯA ĐẠT'}
            </strong>
          </p>
        </>
      )}
      {result.details && (
        <div style={{ marginTop: 12 }}>
          {result.details.map((d, i) => (
            <div key={d.question_id} style={{ padding: '6px 0', borderBottom: '1px solid var(--card-border)' }}>
              Câu {i + 1}: {d.is_correct === null ? 'Chờ chấm' : d.is_correct ? '✓ Đúng' : '✗ Sai'}
              {d.explanation_html && (
                // eslint-disable-next-line react/no-danger
                <div className="muted-note" dangerouslySetInnerHTML={{ __html: d.explanation_html }} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ExamTakingPage() {
  const { attemptId } = useParams()
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(null)
  const [responses, setResponses] = useState({})
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [remainingSec, setRemainingSec] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api.get(`/exams/attempts/${attemptId}/`)
      .then(({ data }) => {
        setAttempt(data)
        setResponses(data.answers || {})
        if (data.time_limit_min) {
          const startedMs = new Date(data.started_at).getTime()
          const deadlineMs = startedMs + data.time_limit_min * 60000
          setRemainingSec(Math.max(0, Math.round((deadlineMs - Date.now()) / 1000)))
        }
      })
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được bài thi.'))
  }, [attemptId])

  useEffect(() => {
    if (remainingSec === null || submitting || result) return
    if (remainingSec <= 0) {
      submit()
      return
    }
    const t = setTimeout(() => setRemainingSec((sec) => sec - 1), 1000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remainingSec, submitting, result])

  async function saveAnswer(questionId, response) {
    setResponses((prev) => ({ ...prev, [questionId]: response }))
    try {
      await api.post(`/exams/attempts/${attemptId}/answer/`, { question: questionId, response })
    } catch {
      // tu luu tam - loi mang se thu lai o lan doi cau tra loi tiep theo, khong chan nguoi thi
    }
  }

  async function submit() {
    setSubmitting(true)
    setError('')
    try {
      const { data } = await api.post(`/exams/attempts/${attemptId}/submit/`)
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không nộp được bài thi.')
    } finally {
      setSubmitting(false)
    }
  }

  const answeredCount = useMemo(
    () => Object.keys(responses).filter((k) => Object.keys(responses[k] || {}).length > 0).length,
    [responses],
  )

  if (error && !attempt) {
    return <AppShell><p style={{ color: 'var(--danger)' }}>{error}</p></AppShell>
  }
  if (!attempt) {
    return <AppShell><p className="muted-note">Đang tải...</p></AppShell>
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Bài thi</h2>
        {remainingSec !== null && !result && (
          <span className="badge badge-warning" style={{ fontSize: 16 }}>⏱ {formatCountdown(remainingSec)}</span>
        )}
      </div>

      {result ? (
        <>
          <ResultView result={result} />
          <button style={{ marginTop: 12 }} onClick={() => navigate('/my-exams')}>
            &larr; Về Bài thi của tôi
          </button>
        </>
      ) : (
        <>
          <p className="muted-note">Đã trả lời {answeredCount}/{attempt.questions.length} câu.</p>
          {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
          {attempt.questions.map((q, i) => (
            <QuestionCard
              key={q.id} index={i} question={q} response={responses[q.id]}
              onChange={(resp) => saveAnswer(q.id, resp)}
            />
          ))}
          <button onClick={() => { if (window.confirm('Nộp bài thi? Không thể sửa sau khi nộp.')) submit() }} disabled={submitting}>
            Nộp bài
          </button>
        </>
      )}
    </AppShell>
  )
}
