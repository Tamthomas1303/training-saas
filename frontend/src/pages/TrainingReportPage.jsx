import { useState } from 'react'
import AppShell from '../components/AppShell'
import api from '../api/client'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function TrainingReportPage() {
  const [kind, setKind] = useState('week')
  const [date, setDate] = useState(todayIso())
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewSubject, setPreviewSubject] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadPreview() {
    setLoading(true)
    setError('')
    setMessage('')
    try {
      const { data } = await api.get('/reports/training/preview/', { params: { kind, date } })
      setPreviewHtml(data.html)
      setPreviewSubject(data.subject)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không xem trước được báo cáo.')
      setPreviewHtml('')
    } finally {
      setLoading(false)
    }
  }

  async function sendEmail() {
    setSending(true)
    setError('')
    setMessage('')
    try {
      const { data } = await api.post('/reports/training/send/', { kind, date })
      setMessage(`Đã gửi email tới: ${data.to.join(', ')}${data.cc.length ? ` (CC: ${data.cc.join(', ')})` : ''}.`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không gửi được email.')
    } finally {
      setSending(false)
    }
  }

  return (
    <AppShell>
      <h2 style={{ marginTop: 0 }}>Báo cáo đào tạo</h2>
      <p className="muted-note" style={{ marginTop: -6 }}>
        Chọn kỳ báo cáo, xem trước rồi gửi email cho danh sách người nhận cấu hình sẵn (REPORT_TO/REPORT_CC).
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="week">Tuần</option>
            <option value="month">Tháng</option>
          </select>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <button onClick={loadPreview} disabled={loading}>
            {loading ? 'Đang tải...' : 'Xem trước'}
          </button>
          <button className="btn-outline" onClick={sendEmail} disabled={sending || !previewHtml}>
            {sending ? 'Đang gửi...' : 'Gửi email'}
          </button>
        </div>
        {error && <p style={{ color: 'var(--danger)', marginTop: 8 }}>{error}</p>}
        {message && <p style={{ marginTop: 8 }}>{message}</p>}
      </div>

      {previewHtml && (
        <div className="card">
          <div className="muted-note" style={{ marginBottom: 8 }}>Tiêu đề email: {previewSubject}</div>
          <iframe
            title="Xem trước báo cáo"
            srcDoc={previewHtml}
            style={{ width: '100%', height: 800, border: '1px solid var(--border, #cfd6d3)', borderRadius: 8 }}
          />
        </div>
      )}
    </AppShell>
  )
}
