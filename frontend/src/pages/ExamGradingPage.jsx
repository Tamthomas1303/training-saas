import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

function GradeModal({ attempt, onClose, onGraded }) {
  const [detail, setDetail] = useState(null)
  const [scores, setScores] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get(`/exams/attempts/${attempt.id}/`).then(({ data }) => setDetail(data))
  }, [attempt.id])

  const essayQuestions = (detail?.questions || []).filter((q) => q.type === 'essay')

  async function save() {
    setSaving(true)
    setError('')
    try {
      await api.post(`/exams/attempts/${attempt.id}/grade/`, { scores })
      onGraded()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không chấm được bài.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title={`Chấm bài — ${attempt.employee_code} ${attempt.employee_name}`} onClose={onClose}>
      {!detail && <p className="muted-note">Đang tải...</p>}
      {detail && essayQuestions.length === 0 && <p className="muted-note">Bài này không có câu tự luận.</p>}
      {essayQuestions.map((q, i) => (
        <div key={q.id} style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4 }}>
            <strong>Câu {i + 1}</strong> ({q.points} điểm)
          </div>
          {/* eslint-disable-next-line react/no-danger */}
          <div dangerouslySetInnerHTML={{ __html: q.stem_html }} style={{ marginBottom: 6 }} />
          <div className="card" style={{ marginBottom: 6, whiteSpace: 'pre-wrap' }}>
            {detail.answers?.[q.id]?.text || <span className="muted-note">(chưa trả lời)</span>}
          </div>
          <input
            type="number" min={0} max={q.points}
            placeholder={`Điểm (0 - ${q.points})`}
            style={{ ...s.input, width: 160 }}
            onChange={(e) => setScores((prev) => ({ ...prev, [q.id]: Number(e.target.value) }))}
          />
        </div>
      ))}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {essayQuestions.length > 0 && (
        <button onClick={save} disabled={saving}>Lưu điểm</button>
      )}
    </Modal>
  )
}

export default function ExamGradingPage() {
  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [grading, setGrading] = useState(null)

  function load() {
    setLoading(true)
    api.get('/exams/grading/')
      .then(({ data }) => setAttempts(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được danh sách chấm bài.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <AppShell>
      <h2>Chấm bài</h2>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {loading && <p className="muted-note">Đang tải...</p>}
      <Table>
        <thead>
          <tr>
            <th>Nhân sự</th><th>Đề thi</th><th>Lần</th><th>Nộp lúc</th><th></th>
          </tr>
        </thead>
        <tbody>
          {attempts.map((a) => (
            <tr key={a.id}>
              <td>{a.employee_code} — {a.employee_name}</td>
              <td>{a.assessment_title}</td>
              <td>{a.attempt_no}</td>
              <td>{a.submitted_at ? new Date(a.submitted_at).toLocaleString('vi-VN') : '-'}</td>
              <td><button className="btn-outline btn-sm" onClick={() => setGrading(a)}>Chấm bài</button></td>
            </tr>
          ))}
          {!loading && attempts.length === 0 && (
            <tr><td colSpan={5} className="muted-note">Không có bài nào chờ chấm.</td></tr>
          )}
        </tbody>
      </Table>

      {grading && (
        <GradeModal
          attempt={grading} onClose={() => setGrading(null)}
          onGraded={() => { setGrading(null); load() }}
        />
      )}
    </AppShell>
  )
}
