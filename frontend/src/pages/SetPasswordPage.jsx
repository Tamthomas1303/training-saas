import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api/client'

// Nhom 3A (Prompt_Nhom3A_Onboarding_TuDong.md muc 3) - trang cong khai dat mat khau lan dau cho
// tai khoan onboarding tu dong tao (link tu email tiep nhan). KHONG can dang nhap - xem
// App.jsx PUBLIC_PREFIXES + backend accounts.views.SetPasswordView (AllowAny).
export default function SetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!token) {
      setError('Đường link không hợp lệ (thiếu token).')
      return
    }
    if (password !== confirm) {
      setError('Xác nhận mật khẩu không khớp.')
      return
    }
    setSubmitting(true)
    try {
      await api.post('/auth/set-password/', { token, new_password: password })
      setDone(true)
      setTimeout(() => navigate('/login'), 1500)
    } catch (err) {
      setError(err.response?.data?.detail || 'Đặt mật khẩu thất bại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">TSM</div>
        <h2 style={{ textAlign: 'center', margin: '0 0 4px' }}>Đặt mật khẩu lần đầu</h2>
        <p className="muted-note" style={{ textAlign: 'center', marginTop: 0, marginBottom: 16 }}>
          Nhập mật khẩu mới cho tài khoản của bạn.
        </p>
        {done ? (
          <p style={{ textAlign: 'center' }}>Đã đặt mật khẩu thành công. Đang chuyển tới trang đăng nhập...</p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
                Mật khẩu mới
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  style={{ display: 'block', width: '100%', paddingRight: 64 }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
                <button
                  type="button"
                  className="btn-outline btn-sm"
                  onClick={() => setShowPassword((v) => !v)}
                  style={{ position: 'absolute', right: 4, top: 4, border: 'none' }}
                >
                  {showPassword ? 'Ẩn' : 'Hiện'}
                </button>
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
                Xác nhận mật khẩu
              </label>
              <input
                type={showPassword ? 'text' : 'password'}
                style={{ display: 'block', width: '100%' }}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>
            {error && (
              <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12 }}>{error}</p>
            )}
            <button type="submit" disabled={submitting} style={{ width: '100%', padding: 10 }}>
              {submitting ? 'Đang lưu...' : 'Đặt mật khẩu'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
