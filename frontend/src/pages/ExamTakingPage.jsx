import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import api from '../api/client'
import { captureSnapshotDataUrl, detectFaceCount, loadFaceApi } from '../utils/proctoring'
import * as s from './listPageStyles'

const FACE_CHECK_INTERVAL_MS = 8000

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

// A2/A3: man dong y truoc khi bat dau bai thi co giam sat - xin quyen camera RO RANG (khong xin
// ngam), giai thich se lam gi (chup anh dinh ky, ghi log roi tab, cam copy/paste). Hoc vien co
// the "Tiep tuc khong dung camera" (mobile/khong co cam/tu choi quyen) - van bi ghi log roi tab
// + chan copy/paste nhu thuong, chi la khong co webcam/snapshot - dung tinh than "ran de, khong
// chan 100%" cua prompt.
function ProctoringConsentGate({ config, onAgree, onSkipCamera, cameraError }) {
  return (
    <div className="card" style={{ maxWidth: 520, margin: '40px auto' }}>
      <h3 style={{ marginTop: 0 }}>Bài thi này có giám sát (proctoring)</h3>
      <ul style={{ paddingLeft: 20, marginBottom: 16 }}>
        <li>Xin quyền dùng camera để chụp ảnh định kỳ (mỗi {config.snapshot_interval_sec} giây) làm bằng chứng.</li>
        <li>Ghi lại thời điểm nếu bạn rời khỏi tab/cửa sổ làm bài{
          config.tab_leave_auto_submit_limit ? ` — rời tab quá ${config.tab_leave_auto_submit_limit} lần sẽ tự động nộp bài` : ''
        }.</li>
        <li>Không cho phép copy/paste/chuột phải trong lúc làm bài.</li>
        {config.require_fullscreen && <li>Yêu cầu làm bài ở chế độ toàn màn hình.</li>}
      </ul>
      {cameraError && <p style={{ color: 'var(--danger)' }}>{cameraError}</p>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={onAgree}>Đồng ý &amp; Bắt đầu</button>
        <button className="btn-outline" onClick={onSkipCamera}>Tiếp tục không dùng camera</button>
      </div>
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

  // Giai doan A - proctoring. proctoringStage: 'none' (de khong bat giam sat - hanh vi CU,
  // khong doi gi) | 'consent' (cho dong y) | 'active' (dang giam sat, co the co hoac khong co
  // camera). videoRef/streamRef/faceApiRef la refs (khong trigger re-render) vi day la tai
  // nguyen trinh duyet (camera stream, model AI), khong phai state hien thi.
  const [proctoringStage, setProctoringStage] = useState('none')
  const [cameraError, setCameraError] = useState('')
  const [fullscreenWarning, setFullscreenWarning] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const faceApiRef = useRef(null)
  const intervalsRef = useRef([])
  const enteredFullscreenRef = useRef(false)
  const listenersCleanupRef = useRef(null)

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
        setProctoringStage(data.proctoring?.enabled ? 'consent' : 'none')
      })
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được bài thi.'))
  }, [attemptId])

  const postProctoringEvent = useCallback(async (type, extra) => {
    try {
      const { data } = await api.post(`/exams/attempts/${attemptId}/proctoring-event/`, { type, ...extra })
      if (data.auto_submitted) {
        setResult(data.result)
      }
    } catch {
      // ghi log ban chung - loi mang khong duoc chan nguoi thi dang lam bai
    }
  }, [attemptId])

  const stopMonitoring = useCallback(() => {
    intervalsRef.current.forEach(clearInterval)
    intervalsRef.current = []
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (listenersCleanupRef.current) {
      listenersCleanupRef.current()
      listenersCleanupRef.current = null
    }
    if (enteredFullscreenRef.current && document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  }, [])

  const attachBehaviorListeners = useCallback(() => {
    const onVisibility = () => { if (document.hidden) postProctoringEvent('tab_leave') }
    const onBlur = () => postProctoringEvent('blur')
    const onContextMenu = (e) => e.preventDefault()
    const onCopyPaste = (e) => e.preventDefault()
    const onFullscreenChange = () => {
      if (enteredFullscreenRef.current && !document.fullscreenElement) {
        setFullscreenWarning(true)
        postProctoringEvent('fullscreen_exit')
      } else if (document.fullscreenElement) {
        setFullscreenWarning(false)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    document.addEventListener('contextmenu', onContextMenu)
    document.addEventListener('copy', onCopyPaste)
    document.addEventListener('cut', onCopyPaste)
    document.addEventListener('paste', onCopyPaste)
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('contextmenu', onContextMenu)
      document.removeEventListener('copy', onCopyPaste)
      document.removeEventListener('cut', onCopyPaste)
      document.removeEventListener('paste', onCopyPaste)
      document.removeEventListener('fullscreenchange', onFullscreenChange)
    }
  }, [postProctoringEvent])

  async function startMonitoring(useCamera) {
    setCameraError('')
    if (attempt.proctoring?.require_fullscreen) {
      try {
        await document.documentElement.requestFullscreen()
        enteredFullscreenRef.current = true
      } catch {
        // trinh duyet/thiet bi khong ho tro fullscreen (vd 1 so mobile) - khong chan bai thi
      }
    }

    if (useCamera) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true })
        streamRef.current = stream
        // videoRef.current con la null luc nay (the <video> chi mount SAU khi setProctoringStage
        // ben duoi kich hoat re-render, dang o man dong y - xem useEffect gan srcObject phia
        // duoi, chay SAU khi <video> da mount).

        const snapshotSec = attempt.proctoring?.snapshot_interval_sec || 45
        intervalsRef.current.push(setInterval(() => {
          if (videoRef.current) {
            postProctoringEvent('snapshot', { image: captureSnapshotDataUrl(videoRef.current) })
          }
        }, snapshotSec * 1000))

        loadFaceApi().then((faceapi) => {
          faceApiRef.current = faceapi
          intervalsRef.current.push(setInterval(async () => {
            if (!videoRef.current) return
            const count = await detectFaceCount(faceapi, videoRef.current).catch(() => null)
            if (count === 0) postProctoringEvent('no_face')
            else if (count > 1) postProctoringEvent('multi_face', { detail: `${count} khuôn mặt` })
          }, FACE_CHECK_INTERVAL_MS))
        }).catch((err) => {
          // Thu vien nhan dien khong tai duoc (mang/CDN) - webcam + snapshot van chay binh
          // thuong, chi mat phan phat hien khuon mat. Khong hien loi chan man hinh.
          console.warn('Không tải được thư viện nhận diện khuôn mặt:', err)
        })
      } catch {
        setCameraError('Không truy cập được camera — vẫn tiếp tục làm bài (không có ảnh chụp/nhận diện khuôn mặt).')
      }
    }

    listenersCleanupRef.current = attachBehaviorListeners()
    setProctoringStage('active')
  }

  useEffect(() => {
    if (proctoringStage !== 'active') return undefined
    return () => stopMonitoring()
  }, [proctoringStage, stopMonitoring])

  // <video> chi mount khi proctoringStage==='active' (xem JSX) - phai gan srcObject SAU khi da
  // mount (trong effect, chay sau commit), khong the gan ngay trong startMonitoring vi luc do
  // videoRef.current van con null (dang o man dong y).
  useEffect(() => {
    if (proctoringStage === 'active' && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [proctoringStage])

  useEffect(() => {
    if (result) stopMonitoring()
  }, [result, stopMonitoring])

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

  if (proctoringStage === 'consent') {
    return (
      <AppShell>
        <ProctoringConsentGate
          config={attempt.proctoring}
          cameraError={cameraError}
          onAgree={() => startMonitoring(true)}
          onSkipCamera={() => startMonitoring(false)}
        />
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Bài thi</h2>
        {remainingSec !== null && !result && (
          <span className="badge badge-warning" style={{ fontSize: 16 }}>⏱ {formatCountdown(remainingSec)}</span>
        )}
      </div>

      {streamRef.current && !result && (
        <div style={{ position: 'fixed', bottom: 12, right: 12, zIndex: 50 }}>
          <video
            ref={videoRef} autoPlay muted playsInline
            style={{ width: 120, height: 90, borderRadius: 8, border: '2px solid var(--forest)', objectFit: 'cover' }}
          />
        </div>
      )}
      {cameraError && !result && <p className="muted-note" style={{ color: 'var(--danger)' }}>{cameraError}</p>}
      {fullscreenWarning && !result && (
        <div className="card" style={{ borderColor: 'var(--danger)', marginBottom: 12 }}>
          Bạn đã thoát chế độ toàn màn hình.{' '}
          <button
            className="btn-outline btn-sm"
            onClick={() => document.documentElement.requestFullscreen?.().then(() => { enteredFullscreenRef.current = true })}
          >
            Vào lại toàn màn hình
          </button>
        </div>
      )}

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
