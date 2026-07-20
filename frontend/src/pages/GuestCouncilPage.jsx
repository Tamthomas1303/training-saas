import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client'
import ScoreForm from '../components/ScoreForm'

// Trang cho người đánh giá KHÁCH MỜI (QC/HCNS...) — mở bằng link token, không cần đăng nhập.
export default function GuestCouncilPage() {
  const { token } = useParams()
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState('')

  useEffect(() => {
    api
      .get(`/evaluation/council-guest/${token}/`)
      .then(({ data }) => setForm(data))
      .catch(() => setError('Link không hợp lệ hoặc đã hết hạn.'))
  }, [token])

  async function submit(scores, dish, sign) {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post(`/evaluation/council-guest/${token}/submit/`, {
        scores, dish_name: dish, sign,
      })
      setDone(
        `Đã gửi. Kết quả: ${data.percent}% (${data.result === 'pass' ? 'Đạt' : 'Chưa đạt'})` +
          (data.dish_name ? ` — món ${data.dish_name}` : '') + '.'
      )
    } catch (e) {
      setError(e.response?.data?.detail || 'Gửi thất bại.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page" style={{ alignItems: 'flex-start', minHeight: '100vh' }}>
      <div className="login-card" style={{ maxWidth: 680, width: '100%', margin: '24px auto' }}>
        {!form && !error && <p>Đang tải phiếu...</p>}
        {error && !form && <p style={{ color: 'var(--danger)' }}>{error}</p>}
        {form && (
          <>
            <h2 style={{ marginTop: 0 }}>
              {form.council_kind === 'skill' ? 'Chấm tay nghề' : 'Phỏng vấn'} — {form.employee.name}
            </h2>
            <p className="muted-note">
              {form.employee.position} · {form.employee.restaurant}
              {form.dept_role ? ` · Vai: ${form.dept_role}` : ''}
            </p>
            {done ? (
              <>
                <p style={{ color: 'var(--forest)', fontWeight: 600 }}>{done}</p>
                {form.council_kind === 'skill' && (
                  <p className="muted-note">
                    Cần chấm thêm món khác? Tải lại trang này rồi nhập bản chấm mới.
                  </p>
                )}
              </>
            ) : (
              <ScoreForm
                criteria={form.criteria}
                showDish={form.council_kind === 'skill'}
                onSubmit={submit}
                busy={busy}
                submitLabel="Gửi kết quả"
              />
            )}
            {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
          </>
        )}
      </div>
    </div>
  )
}
