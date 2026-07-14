import AppShell from '../components/AppShell'
import { useAuth } from '../auth/AuthContext'

export default function DashboardPage() {
  const { user } = useAuth()

  return (
    <AppShell>
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, var(--forest), var(--green))',
          color: '#fff',
          border: 'none',
        }}
      >
        <h2 style={{ color: '#fff', margin: 0 }}>Xin chào, {user.full_name || user.username}</h2>
        <p style={{ margin: '8px 0 0', opacity: 0.9 }}>
          {user.tenant_name} · Vai trò: {user.role}
        </p>
      </div>
    </AppShell>
  )
}
