import { useAuth } from '../auth/AuthContext'

export default function DashboardPage() {
  const { user, logout } = useAuth()

  return (
    <div style={{ maxWidth: 480, margin: '80px auto', fontFamily: 'sans-serif' }}>
      <h2>Xin chào, {user.full_name || user.username}</h2>
      <p>Tenant: {user.tenant_name}</p>
      <p>Vai trò: {user.role}</p>
      <button onClick={logout}>Đăng xuất</button>
    </div>
  )
}
