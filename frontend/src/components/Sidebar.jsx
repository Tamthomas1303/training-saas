import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { ADMIN_NAV } from '../config/adminNav'

// Muc 16 Phase 1 phan B - `overridePaths` (tu RoleMenuConfig, xem AuthContext) khi co thi THAY
// THE hoan toan bo loc `roles` mac dinh (cho phep BAT muc ngoai roles goc - chi doi hien thi,
// ProtectedRoute van chan quyen that su). Khong truyen -> giu dung hanh vi cu.
function itemsForRole(items, role, overridePaths) {
  const list = items || []
  if (overridePaths) {
    const allowed = new Set(overridePaths)
    return list.filter((it) => allowed.has(it.path))
  }
  return list.filter((it) => it.roles.includes(role))
}

function isItemActive(pathname, path) {
  return pathname === path || pathname.startsWith(`${path}/`)
}

// Sidebar console admin - UI dot 2 (Prompt_UI_Dot2_ConsoleAdmin.md muc A). CHI dung cho
// admin/om/bod tren desktop (xem AppShell.jsx) - loc muc theo role giong tinh than
// getMenuForRole (khong hien muc ngoai quyen), tuong tu Route/ProtectedRoute van la lop chan
// that su, sidebar chi la lop hien thi.
// `collapsed`/`onToggleCollapsed` do AppShell giu (khong tu quan ly o day) de con dieu chinh
// margin-left cua noi dung chinh theo dung do rong sidebar hien tai.
export default function Sidebar({ role, collapsed, onToggleCollapsed, overridePaths }) {
  const location = useLocation()

  const groups = ADMIN_NAV.filter((g) => {
    if (g.path) return overridePaths ? overridePaths.includes(g.path) : true
    return itemsForRole(g.items, role, overridePaths).length > 0
  })
  const activeGroupKey = groups.find(
    (g) => !g.path && itemsForRole(g.items, role, overridePaths).some((it) => isItemActive(location.pathname, it.path)),
  )?.key
  const [openGroups, setOpenGroups] = useState(() => new Set(activeGroupKey ? [activeGroupKey] : []))

  function openGroupExpanded(key) {
    setOpenGroups((prev) => new Set(prev).add(key))
  }

  function toggleGroup(key) {
    if (collapsed) {
      onToggleCollapsed()
      openGroupExpanded(key)
      return
    }
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <aside className={`admin-sidebar${collapsed ? ' collapsed' : ''}`}>
      <button
        type="button"
        className="admin-sidebar-toggle"
        onClick={onToggleCollapsed}
        title={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'}
      >
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
      </button>

      <nav className="admin-sidebar-nav">
        {groups.map((g) => {
          const GroupIcon = g.icon

          if (g.path) {
            const active = isItemActive(location.pathname, g.path)
            return (
              <Link key={g.key} to={g.path} className={`admin-sidebar-link${active ? ' active' : ''}`} title={g.title}>
                <GroupIcon size={18} />
                {!collapsed && <span>{g.title}</span>}
              </Link>
            )
          }

          const items = itemsForRole(g.items, role, overridePaths)
          const isOpen = !collapsed && openGroups.has(g.key)
          return (
            <div key={g.key} className="admin-sidebar-group">
              <button type="button" className="admin-sidebar-group-head" onClick={() => toggleGroup(g.key)} title={g.title}>
                <GroupIcon size={18} />
                {!collapsed && (
                  <>
                    <span>{g.title}</span>
                    {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </>
                )}
              </button>
              {isOpen && (
                <div className="admin-sidebar-group-items">
                  {items.map((it) => {
                    const ItemIcon = it.icon
                    const active = isItemActive(location.pathname, it.path)
                    return (
                      <Link key={it.path} to={it.path} className={`admin-sidebar-link${active ? ' active' : ''}`}>
                        <ItemIcon size={16} />
                        <span>{it.label}</span>
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
