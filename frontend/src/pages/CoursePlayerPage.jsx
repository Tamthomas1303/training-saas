import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import ProgressBar from '../components/ProgressBar'
import api from '../api/client'
import { detectFaceCount, loadFaceApi } from '../utils/proctoring'

const STATUS_ICON = { pending: '○', in_progress: '◐', done: '✓' }
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
// Chong tua (Giai doan B): dung y prompt "an toan" hon nguong grace o server (8s) 1 chut, de
// snap-back o UI xay ra som hon la bi server tu choi (server van la lop chan that su).
const SEEK_CLIENT_GRACE_SEC = 5
const FACE_CHECK_INTERVAL_MS = 4000

function youtubeEmbedUrl(url) {
  const match = (url || '').match(/(?:v=|youtu\.be\/|embed\/)([\w-]{6,})/)
  return match ? `https://www.youtube.com/embed/${match[1]}` : url
}

function vimeoEmbedUrl(url) {
  const match = (url || '').match(/vimeo\.com\/(\d+)/)
  return match ? `https://player.vimeo.com/video/${match[1]}` : url
}

// Bai SCORM (Dot 4): trang phat do CHINH Django serve (KHONG phai React) o URL rieng, gan
// window.API bang scorm-again TRUOC KHI tao iframe noi dung - dam bao SCO doc duoc
// window.parent.API cung origin (Django), khong lien quan origin cua trang React nay. Truoc
// khi nhung iframe, phai dam bao co LessonProgress (get_or_create qua /courses/progress/,
// giong logic cac dang bai khac) de lay progress_id dung cho state/commit. JWT truyen qua URL
// FRAGMENT (#token=...) - khong len server qua query string.
function ScormContent({ lesson }) {
  const [progressId, setProgressId] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setProgressId(null)
    setError('')
    api.post('/courses/progress/', { lesson: lesson.id })
      .then(({ data }) => { if (active) setProgressId(data.id) })
      .catch(() => { if (active) setError('Không khởi tạo được tiến trình bài SCORM.') })
    return () => { active = false }
  }, [lesson.id])

  if (error) return <p style={{ color: 'var(--danger)' }}>{error}</p>
  if (!lesson.scorm_package_id) return <p className="muted-note">Bài học chưa có gói SCORM.</p>
  if (!progressId) return <p className="muted-note">Đang tải bài học...</p>

  const token = localStorage.getItem('access_token') || ''
  const src = `${API_BASE}/courses/scorm/${lesson.scorm_package_id}/player/`
    + `?progress=${progressId}#token=${encodeURIComponent(token)}`

  return (
    <iframe
      key={progressId}
      src={src}
      title={lesson.title}
      style={{ width: '100%', height: '70vh', border: 0, background: 'var(--card)' }}
    />
  )
}

function LessonContent({ lesson, onPingVideo }) {
  const videoRef = useRef(null)
  // Giai doan B (Prompt_ChongGianLan_Thi_Video.md) - chi ap dung khi bai la video_r2 VA
  // anti_seek=True (dung 1 co cho ca chan tua lan tu tam dung webcam, khong them toggle rieng).
  const antiSeek = lesson.anti_seek && lesson.type === 'video_r2'
  const maxWatchedRef = useRef(lesson.progress?.max_watched_sec || 0)
  const faceVideoRef = useRef(null)
  const faceStreamRef = useRef(null)
  const faceIntervalRef = useRef(null)
  const noFaceSinceRef = useRef(null)
  const pausedByFaceRef = useRef(false)
  const [faceMonitorOn, setFaceMonitorOn] = useState(false)
  const [faceWarning, setFaceWarning] = useState(false)
  const [pausedByFace, setPausedByFace] = useState(false)
  const [cameraError, setCameraError] = useState('')

  useEffect(() => {
    if (lesson.type !== 'video_r2' || !videoRef.current) return
    const video = videoRef.current
    if (lesson.progress?.last_position_sec) {
      video.currentTime = lesson.progress.last_position_sec
    }
    let lastSent = 0
    function onTimeUpdate() {
      if (Math.abs(video.currentTime - lastSent) < 5) return
      lastSent = video.currentTime
      const pct = video.duration ? Math.round((video.currentTime / video.duration) * 100) : 0
      onPingVideo(Math.round(video.currentTime), pct)
    }
    function onEnded() {
      onPingVideo(Math.round(video.currentTime), 100)
    }
    video.addEventListener('timeupdate', onTimeUpdate)
    video.addEventListener('ended', onEnded)
    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate)
      video.removeEventListener('ended', onEnded)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lesson.id])

  // Muc 1 (chong tua): "tran" cho phep tua la max_watched_sec, LAY TU SERVER (khong chi dua vao
  // JS client - xem services.record_watch_progress) - tach RIENG voi effect timeupdate/ended o
  // tren (khong dong toi luong watched_pct/last_position_sec cu).
  useEffect(() => {
    maxWatchedRef.current = lesson.progress?.max_watched_sec || 0
    if (!antiSeek || !videoRef.current) return undefined
    const video = videoRef.current
    let lastSentAt = -999

    function onTimeUpdateWatch() {
      if (video.seeking || Math.abs(video.currentTime - lastSentAt) < 5) return
      lastSentAt = video.currentTime
      api.post('/courses/watch-progress/', { lesson: lesson.id, position_sec: Math.round(video.currentTime) })
        .then(({ data }) => { maxWatchedRef.current = data.max_watched_sec })
        .catch(() => {})
    }
    function onSeeking() {
      if (video.currentTime > maxWatchedRef.current + SEEK_CLIENT_GRACE_SEC) {
        video.currentTime = maxWatchedRef.current
      }
    }
    video.addEventListener('timeupdate', onTimeUpdateWatch)
    video.addEventListener('seeking', onSeeking)
    return () => {
      video.removeEventListener('timeupdate', onTimeUpdateWatch)
      video.removeEventListener('seeking', onSeeking)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lesson.id, antiSeek])

  function stopFaceMonitor() {
    if (faceIntervalRef.current) { clearInterval(faceIntervalRef.current); faceIntervalRef.current = null }
    if (faceStreamRef.current) { faceStreamRef.current.getTracks().forEach((t) => t.stop()); faceStreamRef.current = null }
    noFaceSinceRef.current = null
    pausedByFaceRef.current = false
    setFaceMonitorOn(false)
    setFaceWarning(false)
    setPausedByFace(false)
  }

  // Doi bai = phai bam bat lai giam sat webcam (dong y ro rang cho TUNG phien, khong am tham
  // giu camera bat xuyen bai).
  useEffect(() => stopFaceMonitor, [lesson.id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (faceMonitorOn && faceStreamRef.current && faceVideoRef.current) {
      faceVideoRef.current.srcObject = faceStreamRef.current
    }
  }, [faceMonitorOn])

  function logWatchEvent(type) {
    api.post('/courses/lesson-watch-event/', { lesson: lesson.id, type }).catch(() => {})
  }

  // Muc 2 (auto-pause theo webcam khi hoc): xin quyen camera RO RANG qua nut bam (khong tu bat).
  // Mat mat ~face_pause_warn_sec giay -> canh bao; ~face_pause_stop_sec giay -> tu tam dung; co
  // mat lai -> tu phat tiep. KHONG chup/luu anh nao (khac man Thi) - chi ghi moc tam dung/tiep tuc.
  async function startFaceMonitor() {
    setCameraError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      faceStreamRef.current = stream
      setFaceMonitorOn(true)
    } catch {
      setCameraError('Không truy cập được camera.')
      return
    }

    loadFaceApi().then((faceapi) => {
      faceIntervalRef.current = setInterval(async () => {
        const video = videoRef.current
        if (!faceVideoRef.current || !video) return
        const count = await detectFaceCount(faceapi, faceVideoRef.current).catch(() => null)
        if (count === null) return
        const warnMs = (lesson.face_pause_warn_sec || 5) * 1000
        const stopMs = (lesson.face_pause_stop_sec || 10) * 1000

        if (count === 0) {
          if (!noFaceSinceRef.current) noFaceSinceRef.current = Date.now()
          const missingMs = Date.now() - noFaceSinceRef.current
          if (missingMs >= stopMs && !pausedByFaceRef.current && !video.paused) {
            video.pause()
            pausedByFaceRef.current = true
            setPausedByFace(true)
            setFaceWarning(false)
            logWatchEvent('paused_face_lost')
          } else if (missingMs >= warnMs) {
            setFaceWarning(true)
          }
        } else {
          if (pausedByFaceRef.current) {
            pausedByFaceRef.current = false
            setPausedByFace(false)
            logWatchEvent('resumed')
            video.play().catch(() => {})
          }
          noFaceSinceRef.current = null
          setFaceWarning(false)
        }
      }, FACE_CHECK_INTERVAL_MS)
    }).catch((err) => {
      // Thu vien nhan dien khong tai duoc (mang/CDN) - webcam preview van hien, chi mat phan
      // tu tam dung theo mat. Khong chan viec hoc.
      console.warn('Không tải được thư viện nhận diện khuôn mặt:', err)
    })
  }

  switch (lesson.type) {
    case 'video_r2':
      return (
        <div>
          {antiSeek && (
            <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {!faceMonitorOn ? (
                <button className="btn-outline btn-sm" onClick={startFaceMonitor}>
                  Bật giám sát tập trung (webcam)
                </button>
              ) : (
                <>
                  <video
                    ref={faceVideoRef} autoPlay muted playsInline
                    style={{ width: 72, height: 54, borderRadius: 6, objectFit: 'cover', border: '1px solid var(--card-border)' }}
                  />
                  <button className="btn-outline btn-sm" onClick={stopFaceMonitor}>Tắt giám sát</button>
                </>
              )}
              {cameraError && <span className="muted-note" style={{ color: 'var(--danger)' }}>{cameraError}</span>}
              {faceWarning && !pausedByFace && (
                <span className="badge badge-warning">Không thấy bạn trước camera — video sẽ tạm dừng nếu tiếp tục mất mặt.</span>
              )}
              {pausedByFace && (
                <span className="badge badge-danger">Đã tạm dừng vì không thấy bạn trước camera — quay lại để phát tiếp.</span>
              )}
            </div>
          )}
          <video ref={videoRef} src={lesson.content_url} controls style={{ width: '100%', maxHeight: '60vh', background: '#000' }} />
        </div>
      )
    case 'video_youtube':
      return (
        <iframe
          src={youtubeEmbedUrl(lesson.content_url)}
          title={lesson.title}
          style={{ width: '100%', aspectRatio: '16/9', border: 0 }}
          allow="autoplay; encrypted-media; picture-in-picture"
          allowFullScreen
        />
      )
    case 'video_vimeo':
      return (
        <iframe
          src={vimeoEmbedUrl(lesson.content_url)}
          title={lesson.title}
          style={{ width: '100%', aspectRatio: '16/9', border: 0 }}
          allow="autoplay; encrypted-media; picture-in-picture"
          allowFullScreen
        />
      )
    case 'pdf':
      return <iframe src={lesson.content_url} title={lesson.title} style={{ width: '100%', height: '70vh', border: 0 }} />
    case 'text':
      // eslint-disable-next-line react/no-danger
      return <div className="card" dangerouslySetInnerHTML={{ __html: lesson.content_html || '' }} />
    case 'link':
      return (
        <div className="card">
          <a href={lesson.content_url} target="_blank" rel="noreferrer">
            {lesson.content_url}
          </a>
        </div>
      )
    case 'scorm':
      return <ScormContent lesson={lesson} />
    default:
      return null
  }
}

export default function CoursePlayerPage() {
  const { courseId } = useParams()
  const [course, setCourse] = useState(null)
  const [error, setError] = useState('')
  const [activeLessonId, setActiveLessonId] = useState(null)
  const [marking, setMarking] = useState(false)

  function load(keepActive) {
    api
      .get(`/courses/my/${courseId}/`)
      .then(({ data }) => {
        setCourse(data)
        if (!keepActive) {
          const firstLesson = data.modules.flatMap((m) => m.lessons)[0]
          setActiveLessonId(firstLesson?.id ?? null)
        }
      })
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được khóa học.'))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(false), [courseId])

  // Bai SCORM bao hoan thanh tu trang phat (Django, khac origin) qua postMessage - tai lai
  // tien do de UI (% khoa, nhan "Da hoan thanh") cap nhat ngay, khong can hoc vien tu reload.
  useEffect(() => {
    function onMessage(event) {
      if (event.data?.type === 'scorm-completed') load(true)
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId])

  const allLessons = useMemo(() => course?.modules.flatMap((m) => m.lessons) || [], [course])
  const activeLesson = allLessons.find((l) => l.id === activeLessonId)

  async function saveProgress(payload) {
    await api.post('/courses/progress/', { lesson: activeLessonId, ...payload })
    load(true)
  }

  async function markDone() {
    setMarking(true)
    try {
      await saveProgress({ mark_done: true })
    } finally {
      setMarking(false)
    }
  }

  function pingVideo(lastPositionSec, watchedPct) {
    api.post('/courses/progress/', {
      lesson: activeLessonId, last_position_sec: lastPositionSec, watched_pct: watchedPct,
    })
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
      <Link to="/my-courses">&larr; Khóa học của tôi</Link>
      <h2 style={{ marginTop: 8, marginBottom: 4 }}>{course.title}</h2>
      <ProgressBar percent={course.progress_percent} />
      <div className="muted-note" style={{ marginBottom: 16 }}>
        {course.progress_percent}% hoàn thành
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '2 1 480px', minWidth: 280 }}>
          {activeLesson ? (
            <>
              <h3 style={{ marginTop: 0 }}>{activeLesson.title}</h3>
              <LessonContent lesson={activeLesson} onPingVideo={pingVideo} />
              <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                {activeLesson.progress?.status === 'done' ? (
                  <span style={{ color: 'var(--forest-dark)' }}>
                    ✓{' '}
                    {activeLesson.progress?.completed_offline
                      ? `Hoàn thành offline (xác nhận bởi ${activeLesson.progress.offline_confirmed_by_name || '—'} — ${
                          activeLesson.progress.offline_confirmed_at
                            ? new Date(activeLesson.progress.offline_confirmed_at).toLocaleDateString('vi-VN')
                            : ''
                        })`
                      : 'Đã hoàn thành'}
                  </span>
                ) : activeLesson.type === 'scorm' ? (
                  <span className="muted-note">Hoàn thành tự động khi làm xong nội dung SCORM ở trên.</span>
                ) : (
                  activeLesson.complete_rule !== 'watch_pct' && (
                    <button onClick={markDone} disabled={marking}>
                      Đánh dấu hoàn thành
                    </button>
                  )
                )}
                {activeLesson.complete_rule === 'watch_pct' && activeLesson.progress?.status !== 'done' && (
                  <span className="muted-note">
                    Xem đủ {activeLesson.pass_watch_pct}% video để tự động hoàn thành (đã xem{' '}
                    {activeLesson.progress?.watched_pct ?? 0}%).
                  </span>
                )}
              </div>
            </>
          ) : (
            <p className="muted-note">Khóa học chưa có bài nào.</p>
          )}
        </div>

        <div className="card" style={{ flex: '1 1 260px', minWidth: 240 }}>
          {course.modules.map((m) => (
            <div key={m.id} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{m.title}</div>
              {m.lessons.map((l) => (
                <div
                  key={l.id}
                  onClick={() => setActiveLessonId(l.id)}
                  style={{
                    padding: '6px 8px', cursor: 'pointer', borderRadius: 6,
                    background: l.id === activeLessonId ? 'var(--mint)' : 'transparent',
                    display: 'flex', gap: 6, alignItems: 'center',
                  }}
                >
                  <span>{STATUS_ICON[l.progress?.status || 'pending']}</span>
                  <span>{l.title}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  )
}
