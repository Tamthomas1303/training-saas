import { useAuth } from '../auth/AuthContext'
import { getMenuForRole, isMobileRole } from '../config/menu'
import BottomNav from './BottomNav'
import NotificationsBell from './NotificationsBell'
import OfflineBadge from './OfflineBadge'
import TopBar from './TopBar'

// UI dot 1 (Prompt_UI_Dot1_Theme.md muc 3c): "ten he thong + logo dat vao TopBar (desktop) va
// mobile-topstrip (mobile)" - mobile-topstrip truoc day chi co ten nguoi dung, them nhan
// thuong hieu nho o dau (khong doi bo cuc/cac phan tu con lai).
export default function AppShell({ children }) {
  const { user, brand, logout } = useAuth()
  const role = user?.role || ''
  const menu = getMenuForRole(role)

  if (isMobileRole(role)) {
    return (
      <div>
        <div className="mobile-topstrip">
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            {brand?.logo_url && <img src={brand.logo_url} alt="" style={{ height: 18, width: 'auto' }} />}
            <span className="topbar-user">{user?.full_name || user?.username}</span>
          </span>
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
