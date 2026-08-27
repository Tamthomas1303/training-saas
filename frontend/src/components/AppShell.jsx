import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { getMenuForRole, isMobileRole } from '../config/menu'
import BottomNav from './BottomNav'
import HeaderSearch from './HeaderSearch'
import NotificationsBell from './NotificationsBell'
import OfflineBadge from './OfflineBadge'
import PushToggleButton from './PushToggleButton'
import Sidebar from './Sidebar'
import UserMenu from './UserMenu'

// UI dot 1 (Prompt_UI_Dot1_Theme.md muc 3c): "ten he thong + logo dat vao TopBar (desktop) va
// mobile-topstrip (mobile)" - mobile-topstrip truoc day chi co ten nguoi dung, them nhan
// thuong hieu nho o dau (khong doi bo cuc/cac phan tu con lai).
//
// UI dot 2 (Prompt_UI_Dot2_ConsoleAdmin.md muc A): nhanh desktop (role admin/om/bod - phan con
// lai cua isMobileRole) thay TopBar ngang bang Sidebar 8 nhom gap duoc + topbar mong (tim kiem/
// chuong/user menu/ten he thong). Nhanh mobile GIU NGUYEN 100% - TUYET DOI khong doi bo cuc man
// van hanh, chi nhan theme tu dot 1 (mau/font qua bien CSS, khong dung component/CSS moi cua
// dot nay).
export default function AppShell({ children }) {
  const { user, brand, logout } = useAuth()
  const role = user?.role || ''
  const menu = getMenuForRole(role)
  const [collapsed, setCollapsed] = useState(false)

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
            <PushToggleButton />
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
    <div className="admin-shell">
      <Sidebar role={role.toLowerCase()} collapsed={collapsed} onToggleCollapsed={() => setCollapsed((c) => !c)} />
      <div className={`admin-shell-main${collapsed ? ' collapsed' : ''}`}>
        <header className="admin-topbar-thin">
          <div className="admin-topbar-thin-brand">
            {brand?.logo_url && <img src={brand.logo_url} alt="" style={{ height: 22, width: 'auto' }} />}
            {brand?.system_name || 'Training System Manager'}
          </div>
          <div className="admin-topbar-thin-actions">
            <HeaderSearch />
            <OfflineBadge />
            <NotificationsBell />
            <UserMenu />
            <button className="btn-outline btn-sm" onClick={logout}>
              Đăng xuất
            </button>
          </div>
        </header>
        <main className="app-content-desktop">{children}</main>
      </div>
    </div>
  )
}
