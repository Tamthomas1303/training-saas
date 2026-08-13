import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import ProgressBar from '../components/ProgressBar'
import api from '../api/client'

const STATUS_ICON = { pending: '○', in_progress: '◐', done: '✓' }

function youtubeEmbedUrl(url) {
  const match = (url || '').match(/(?:v=|youtu\.be\/|embed\/)([\w-]{6,})/)
  return match ? `https://www.youtube.com/embed/${match[1]}` : url
}

function vimeoEmbedUrl(url) {
  const match = (url || '').match(/vimeo\.com\/(\d+)/)
  return match ? `https://player.vimeo.com/video/${match[1]}` : url
}

function LessonContent({ lesson, onPingVideo }) {
  const videoRef = useRef(null)

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

  switch (lesson.type) {
    case 'video_r2':
      return (
        <video ref={videoRef} src={lesson.content_url} controls style={{ width: '100%', maxHeight: '60vh', background: '#000' }} />
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
                    background: l.id === activeLessonId ? 'var(--card-hover, #eef3f1)' : 'transparent',
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
