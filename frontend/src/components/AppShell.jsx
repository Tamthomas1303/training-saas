import { useAuth } from '../auth/AuthContext'
import { getMenuForRole, isMobileRole } from '../config/menu'
import BottomNav from './BottomNav'
import NotificationsBell from './NotificationsBell'
import OfflineBadge from './OfflineBadge'
import TopBar from './TopBar'

export default function AppShell({ children }) {
  const { user, logout } = useAuth()
  const role = user?.role || ''
  const menu = getMenuForRole(role)

  if (isMobileRole(role)) {
    return (
      <div>
        <div className="mobile-topstrip">
          <span className="topbar-user">{user?.full_name || user?.username}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <OfflineBadge />
            <NotificationsBell />
            <button className="btn-outline btn-sm" onClick={logout}>
              Đăng xuất
            </button>
          </div>
        </div>
        <main className="app-content-mobile">{children}</main>
        <BottomNav menu={menu} />
      </div>
    )
  }

  return (
    <div>
      <TopBar menu={menu} user={user} onLogout={logout} />
      <main className="app-content-desktop">{children}</main>
    </div>
  )
}
