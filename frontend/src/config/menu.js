// Ban do menu theo vai tro - port tinh than Code.gs::_menusForRole (03_THIET_KE_GIAO_DIEN.md
// muc 3-4), anh xa sang cac trang thuc te da dung trong he thong nay (chua co man Documents/
// Users rieng nen tam khong dua vao menu - se bo sung o dot sau).
export const MENU_ITEMS = {
  hub: { label: 'Trung tâm', icon: '🗂️', path: '/hub' },
  home: { label: 'Trang chủ', icon: '🏠', path: '/' },
  dashboard: { label: 'Dashboard', icon: '📊', path: '/dashboard' },
  students: { label: 'Nhân sự', icon: '👥', path: '/employees' },
  checklist: { label: 'Checklist', icon: '📋', path: '/checklist' },
  training: { label: 'Đào tạo', icon: '🎓', path: '/training' },
  evaluation: { label: 'Đánh giá', icon: '✅', path: '/evaluation' },
  kpi: { label: 'KPI', icon: '📈', path: '/kpi' },
  kpiDashboard: { label: 'Thống kê KPI', icon: '📊', path: '/kpi-dashboard' },
  commission: { label: 'Phụ cấp', icon: '💰', path: '/commission' },
  documents: { label: 'Tài liệu', icon: '📁', path: '/documents' },
  users: { label: 'Người dùng', icon: '🧑‍💼', path: '/users' },
  criteria: { label: 'Tiêu chí', icon: '📝', path: '/criteria' },
  levelup: { label: 'Thăng tiến', icon: '🚀', path: '/levelup' },
  sourcing: { label: 'ĐT nguồn', icon: '🎯', path: '/sourcing' },
}

// Vai tro "toan he thong" -> shell desktop (topbar); con lai -> shell mobile (bottom-nav).
const MOBILE_ROLES = new Set(['trainer', 'bql', 'am', 'kcs'])

// M3 — Card Nesting: các chức năng theo vòng đời đào tạo (nhân sự mới / thăng tiến / nguồn / cấp
// trung) gom vào "Trung tâm" (hub, thẻ cha → thẻ con). Thanh nav phẳng chỉ giữ hub + các mục
// tiện ích toàn cục (dashboard/home, KPI, phụ cấp, tài liệu, người dùng).
const ROLE_MENU = {
  admin: ['hub', 'dashboard', 'kpi', 'kpiDashboard', 'commission', 'documents', 'users'],
  om: ['hub', 'dashboard', 'kpi', 'kpiDashboard', 'commission', 'documents'],
  bod: ['hub', 'dashboard', 'kpi', 'kpiDashboard', 'commission', 'documents'],
  am: ['hub', 'home', 'kpi', 'documents'],
  kcs: ['hub', 'home', 'kpi', 'documents'],
  bql: ['hub', 'home', 'kpi', 'documents'],
  trainer: ['hub', 'home', 'documents'],
}

export function isMobileRole(role) {
  return MOBILE_ROLES.has((role || '').toLowerCase())
}

export function getMenuForRole(role) {
  const keys = ROLE_MENU[(role || '').toLowerCase()] || ROLE_MENU.trainer
  return keys.map((key) => ({ key, ...MENU_ITEMS[key] }))
}
