import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/')
    } catch {
      setError('Sai tên đăng nhập hoặc mật khẩu.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">TS</div>
        <h2 style={{ textAlign: 'center', marginTop: 0 }}>Đăng nhập</h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
              Tên đăng nhập
            </label>
            <input
              style={{ display: 'block', width: '100%' }}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
              Mật khẩu
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                style={{ display: 'block', width: '100%', paddingRight: 64 }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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
          {error && (
            <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12 }}>{error}</p>
          )}
          <button type="submit" disabled={submitting} style={{ width: '100%', padding: 10 }}>
            {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
      </div>
    </div>
  )
}
