import { useEffect, useState } from 'react'
import api from '../api/client'
import { submitGuarded } from '../utils/offlineQueue'
import SignaturePad from './SignaturePad'

const ASPECTS = [
  { id: 'COUNCIL_TAYNGHE', name: 'Tay nghề chuyên môn' },
  { id: 'COUNCIL_DAOTAO', name: 'Kỹ năng đào tạo' },
  { id: 'COUNCIL_VANHANH', name: 'Vận hành ca' },
]

export default function CouncilForm({ employeeId }) {
  const [summary, setSummary] = useState(null)
  const [scores, setScores] = useState({ COUNCIL_TAYNGHE: 80, COUNCIL_DAOTAO: 80, COUNCIL_VANHANH: 80 })
  const [signature, setSignature] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  function loadSummary() {
    api.get('/evaluation/council/', { params: { employee: employeeId } }).then(({ data }) => setSummary(data))
  }

  useEffect(() => {
    loadSummary()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId])

  async function submitScore() {
    setSaving(true)
    setError('')
    setMessage('')
    await submitGuarded(
      'council',
      (payload) => api.post('/evaluation/council/save/', payload).then((r) => r.data),
      { employee: employeeId, scores, sign_evaluator: signature },
      {
        onOk: () => {
          setMessage('Đã gửi điểm hội đồng.')
          loadSummary()
        },
        onErr: setError,
        onQueued: () => setMessage('Mất mạng - đã lưu nháp offline, sẽ tự đồng bộ khi có mạng.'),
      }
    )
    setSaving(false)
  }

  async function finalize() {
    setError('')
    setMessage('')
    try {
      const { data } = await api.post('/evaluation/council/finalize/', { employee: employeeId })
      setMessage(`Đã chốt hội đồng: Tay nghề ${data.tay_nghe}% (${data.skill_result}), Vận hành ${data.van_hanh}% (${data.shift_ops}).`)
      loadSummary()
    } catch (err) {
      setError(err.response?.data?.detail || 'Chốt hội đồng thất bại.')
    }
  }

  if (!summary) return <p>Đang tải hội đồng...</p>

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginTop: 16, background: '#fbfbfe' }}>
      <h4>Hội đồng đánh giá cấp quản lý</h4>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        {summary.aspects.map((a) => (
          <div key={a.id} style={{ border: '1px solid #eee', borderRadius: 6, padding: 8, minWidth: 140, textAlign: 'center' }}>
            <div style={{ fontSize: 12, color: '#666' }}>{a.name}</div>
            <div style={{ fontSize: 20, fontWeight: 'bold' }}>{a.avg}%</div>
            <div style={{ fontSize: 11, color: '#999' }}>{a.count} giám khảo</div>
          </div>
        ))}
        <div style={{ border: '1px solid #eee', borderRadius: 6, padding: 8, minWidth: 140, textAlign: 'center' }}>
          <div style={{ fontSize: 12, color: '#666' }}>Tổng hợp</div>
          <div style={{ fontSize: 20, fontWeight: 'bold' }}>{summary.overall}%</div>
          <div style={{ fontSize: 11, color: '#999' }}>{summary.judge_count} giám khảo</div>
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: '#666', marginBottom: 4 }}>Giám khảo đã chấm:</div>
        {summary.judges.length === 0 && <div style={{ fontSize: 13, color: '#999' }}>Chưa có giám khảo nào chấm.</div>}
        {summary.judges.map((j) => (
          <div key={j.evaluator_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span>
              {j.name} <span style={{ color: '#999' }}>({j.role})</span>
            </span>
            <span style={{ fontWeight: 'bold' }}>{j.overall}%</span>
          </div>
        ))}
      </div>

      <h5>Chấm điểm của bạn</h5>
      {ASPECTS.map((a) => (
        <div key={a.id} style={{ marginBottom: 8 }}>
          <label style={{ display: 'block', fontSize: 13, color: '#666' }}>{a.name} (0–100)</label>
          <input
            type="number"
            min="0"
            max="100"
            value={scores[a.id]}
            onChange={(e) => setScores((s) => ({ ...s, [a.id]: Number(e.target.value) }))}
            style={{ width: 100, padding: 6 }}
          />
        </div>
      ))}

      <div style={{ margin: '12px 0' }}>
        <SignaturePad label="Chữ ký giám khảo" value={signature} onChange={setSignature} />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button disabled={saving} onClick={submitScore}>
          Gửi điểm
        </button>
        <button onClick={finalize}>Chốt hội đồng</button>
      </div>

      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && <p style={{ color: 'green' }}>{message}</p>}
    </div>
  )
}
