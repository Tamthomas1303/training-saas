import { useMemo, useState } from 'react'
import SignaturePad from './SignaturePad'

/**
 * Form chấm điểm dùng chung cho: vận hành ca (Đạt/Không, max=1), tay nghề & phỏng vấn (1–4).
 * Tự nhận diện thang điểm theo max_score của tiêu chí.
 */
export default function ScoreForm({
  criteria = [], showDish = false, initialScores = {}, initialDish = '',
  onSubmit, busy = false, submitLabel = 'Gửi điểm',
}) {
  const [scores, setScores] = useState(initialScores)
  const [dish, setDish] = useState(initialDish)
  const [sign, setSign] = useState('')

  const bySection = useMemo(() => {
    const g = {}
    for (const c of criteria) {
      const s = c.section || 'Tiêu chí'
      ;(g[s] = g[s] || []).push(c)
    }
    return g
  }, [criteria])

  const total = criteria.reduce((s, c) => s + (Number(scores[c.criteria_id]) || 0), 0)
  const maxTotal = criteria.reduce((s, c) => s + c.max_score, 0)
  const percent = maxTotal ? Math.round((total / maxTotal) * 100) : 0
  const pass = percent >= 80

  function setScore(id, v) {
    setScores((s) => ({ ...s, [id]: v }))
  }

  return (
    <div>
      {showDish && (
        <label style={{ display: 'block', marginBottom: 10 }}>
          Món dự thi
          <input
            style={{ display: 'block', width: '100%' }}
            value={dish}
            onChange={(e) => setDish(e.target.value)}
            placeholder="Tên món cho bản chấm này..."
          />
        </label>
      )}

      {Object.entries(bySection).map(([section, items]) => (
        <div key={section} style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 700, color: 'var(--muted)', margin: '6px 0' }}>{section}</div>
          {items.map((c) => (
            <div
              key={c.criteria_id}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid var(--card-border)' }}
            >
              <span style={{ flex: 1, fontSize: 14 }}>{c.content}</span>
              {c.max_score === 1 ? (
                <span style={{ display: 'flex', gap: 4 }}>
                  <button
                    type="button"
                    className={`btn-sm ${Number(scores[c.criteria_id]) === 1 ? '' : 'btn-outline'}`}
                    onClick={() => setScore(c.criteria_id, 1)}
                  >
                    Đạt
                  </button>
                  <button
                    type="button"
                    className={`btn-sm ${scores[c.criteria_id] === 0 ? '' : 'btn-outline'}`}
                    onClick={() => setScore(c.criteria_id, 0)}
                  >
                    Không
                  </button>
                </span>
              ) : (
                <input
                  type="number"
                  min="0"
                  max={c.max_score}
                  value={scores[c.criteria_id] ?? ''}
                  onFocus={(e) => e.target.select()}
                  onChange={(e) => {
                    const raw = Number(e.target.value)
                    setScore(c.criteria_id, Math.max(0, Math.min(c.max_score, Number.isNaN(raw) ? 0 : raw)))
                  }}
                  style={{ width: 60 }}
                  placeholder={`0–${c.max_score}`}
                />
              )}
            </div>
          ))}
        </div>
      ))}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', margin: '10px 0', fontWeight: 700 }}>
        <span>Tổng: {total}/{maxTotal}</span>
        <span style={{ color: pass ? 'var(--forest)' : 'var(--danger)' }}>{percent}% — {pass ? 'Đạt' : 'Chưa đạt'}</span>
      </div>

      <div style={{ margin: '10px 0' }}>
        <SignaturePad label="Chữ ký người đánh giá" value={sign} onChange={setSign} />
      </div>

      <button disabled={busy} onClick={() => onSubmit(scores, dish, sign)}>
        {busy ? 'Đang gửi...' : submitLabel}
      </button>
    </div>
  )
}
