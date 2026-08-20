import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import api from '../api/client'

export default function MyExamsPage() {
  const navigate = useNavigate()
  const [assessments, setAssessments] = useState(null)
  const [error, setError] = useState('')
  const [startingId, setStartingId] = useState(null)

  function load() {
    api.get('/exams/my/')
      .then(({ data }) => setAssessments(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được danh sách đề thi.'))
  }

  useEffect(load, [])

  async function start(assessmentId, hasPassword) {
    let password
    if (hasPassword) {
      password = window.prompt('Đề thi này yêu cầu mật khẩu vào đề:')
      if (password === null) return // huy
    }
    setStartingId(assessmentId)
    try {
      const { data } = await api.post(`/exams/my/${assessmentId}/start/`, password ? { password } : {})
      navigate(`/my-exams/attempt/${data.attempt_id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không bắt đầu được bài thi.')
      setStartingId(null)
    }
  }

  return (
    <AppShell>
      <h2>Bài thi của tôi</h2>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!error && !assessments && <p className="muted-note">Đang tải...</p>}
      {assessments && assessments.length === 0 && <p className="muted-note">Bạn chưa được gán đề thi nào.</p>}

      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
        {assessments?.map((a) => {
          const exhausted = a.attempts_used >= a.max_attempts
          const result = a.last_result
          return (
            <div key={a.assignment_id} className="card">
              <strong>{a.title}</strong>
              <div className="muted-note" style={{ fontSize: 12, margin: '4px 0 8px' }}>
                {a.time_limit_min ? `${a.time_limit_min} phút · ` : ''}
                Đã làm {a.attempts_used}/{a.max_attempts} lần
                {a.due_date ? ` · Hạn: ${a.due_date}` : ''}
              </div>
              {result && (
                <div style={{ marginBottom: 8 }}>
                  {result.percent !== null && result.percent !== undefined ? (
                    <Badge variant={result.passed ? 'success' : 'danger'}>
                      {result.passed ? 'Đạt' : 'Chưa đạt'} — {result.percent}%
                    </Badge>
                  ) : (
                    <Badge variant="neutral">Chờ chấm tự luận</Badge>
                  )}
                </div>
              )}
              {a.in_progress_attempt_id ? (
                <button onClick={() => navigate(`/my-exams/attempt/${a.in_progress_attempt_id}`)}>
                  Tiếp tục làm bài
                </button>
              ) : (
                <button
                  onClick={() => start(a.assessment_id, a.has_password)}
                  disabled={exhausted || startingId === a.assessment_id}
                >
                  {exhausted ? 'Đã hết lượt' : a.has_password ? '🔒 Bắt đầu làm bài' : 'Bắt đầu làm bài'}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </AppShell>
  )
}
