import NavBar from '../components/NavBar'
import { useAuth } from '../auth/AuthContext'
import { page } from './listPageStyles'

export default function DashboardPage() {
  const { user } = useAuth()

  return (
    <div style={page}>
      <NavBar />
      <h2>Xin chào, {user.full_name || user.username}</h2>
      <p>Tenant: {user.tenant_name}</p>
      <p>Vai trò: {user.role}</p>
    </div>
  )
}
