import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import ProgressBar from '../components/ProgressBar'
import api from '../api/client'

const STATUS_VARIANTS = { assigned: 'neutral', in_progress: 'mint', completed: 'success' }

export default function MyCoursesPage() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/courses/my/')
      .then(({ data }) => setCourses(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được danh sách khóa học.'))
  }, [])

  return (
    <AppShell>
      <h2>Khóa học của tôi</h2>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!error && !courses && <p className="muted-note">Đang tải...</p>}

      {courses && courses.length === 0 && (
        <p className="muted-note">Bạn chưa được gán khóa học nào.</p>
      )}

      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
        {courses?.map((c) => (
          <div
            key={c.enrollment_id}
            className="card"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/my-courses/${c.course_id}`)}
          >
            {c.cover_url && (
              <img
                src={c.cover_url}
                alt={c.title}
                style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 8, marginBottom: 8 }}
              />
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <strong>{c.title}</strong>
              <Badge variant={STATUS_VARIANTS[c.status] || 'neutral'}>{c.status_display}</Badge>
            </div>
            <ProgressBar percent={c.progress_percent} />
            <div className="muted-note" style={{ fontSize: 12, marginTop: 4 }}>
              {c.progress_percent}% hoàn thành{c.due_date ? ` · Hạn: ${c.due_date}` : ''}
            </div>
          </div>
        ))}
      </div>
    </AppShell>
  )
}
