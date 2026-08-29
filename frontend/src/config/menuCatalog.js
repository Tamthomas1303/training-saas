// Muc 16 Phase 1 phan B (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md) - danh muc GOP tat ca cac
// "the/man" tung xuat hien trong ca 2 cau hinh dieu huong (menu.js danh cho shell mobile,
// adminNav.js danh cho shell desktop admin/om/bod), dung lam COT cho ma tran cau hinh
// (SettingsPage.jsx tab "Cau hinh menu"). Khoa la ROUTE PATH (duy nhat o ca 2 noi).
import { ADMIN_NAV } from './adminNav'
import { MENU_ITEMS, ROLE_MENU, isMobileRole } from './menu'

function buildCatalog() {
  const map = new Map()
  for (const group of ADMIN_NAV) {
    if (group.path) map.set(group.path, group.title)
    for (const item of group.items || []) {
      if (!map.has(item.path)) map.set(item.path, item.label)
    }
  }
  for (const item of Object.values(MENU_ITEMS)) {
    if (!map.has(item.path)) map.set(item.path, item.label)
  }
  return Array.from(map.entries()).map(([path, label]) => ({ path, label }))
}

export const MENU_CATALOG = buildCatalog()

// 'employee' (hoc vien) KHONG dua vao ma tran - pham vi API cua vai tro nay bi khoa cung qua
// accounts.permissions.EmployeeLearnerScope (frontend AuthContext CHU DINH khong goi endpoint
// cau hinh menu cho vai tro nay - xem loadRoleMenuConfig), nen cau hinh o day se KHONG co tac
// dung gi voi tai khoan hoc vien.
// Phai khop DUNG voi backend accounts.services.ADMIN_CORE_MENU_PATHS - cac the Admin luon duoc
// giu (server tu dong them lai neu thieu), disable checkbox tuong ung o ma tran de khong gay
// hieu lam la tat duoc.
export const ADMIN_CORE_MENU_PATHS = ['/settings', '/users', '/']

export const CONFIGURABLE_ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'om', label: 'OM' },
  { value: 'bod', label: 'BOD' },
  { value: 'am', label: 'AM' },
  { value: 'kcs', label: 'KCS' },
  { value: 'bql', label: 'BQL' },
  { value: 'trainer', label: 'Trainer' },
]

// Mac dinh HIEN TAI (chua cau hinh rieng) cua 1 (role, path) - dung de tich san checkbox trong
// ma tran. admin/om/bod dung shell desktop (Sidebar/adminNav.js); am/kcs/bql/trainer dung shell
// mobile (BottomNav/menu.js) - doc DUNG nguon dang "song" that su cho vai tro do (xem
// components/AppShell.jsx: chi 1 trong 2 shell duoc dung tuy role).
export function isEnabledByDefault(role, path) {
  const r = (role || '').toLowerCase()
  if (isMobileRole(r)) {
    const keys = ROLE_MENU[r] || []
    return keys.some((key) => MENU_ITEMS[key]?.path === path)
  }
  for (const group of ADMIN_NAV) {
    if (group.path === path) return (group.roles || []).includes(r)
    for (const item of group.items || []) {
      if (item.path === path && item.roles.includes(r)) return true
    }
  }
  return false
}
