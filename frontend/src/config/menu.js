// Ban do menu theo vai tro - port tinh than Code.gs::_menusForRole (03_THIET_KE_GIAO_DIEN.md
// muc 3-4), anh xa sang cac trang thuc te da dung trong he thong nay (chua co man Documents/
// Users rieng nen tam khong dua vao menu - se bo sung o dot sau).
export const MENU_ITEMS = {
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
}

// Vai tro "toan he thong" -> shell desktop (topbar); con lai -> shell mobile (bottom-nav).
const MOBILE_ROLES = new Set(['trainer', 'bql', 'am', 'kcs'])

const ROLE_MENU = {
  admin: ['dashboard', 'students', 'checklist', 'evaluation', 'levelup', 'kpi', 'kpiDashboard', 'commission', 'documents', 'criteria', 'users'],
  om: ['dashboard', 'students', 'checklist', 'evaluation', 'levelup', 'kpi', 'kpiDashboard', 'commission', 'documents', 'criteria'],
  bod: ['dashboard', 'students', 'checklist', 'kpi', 'kpiDashboard', 'commission', 'documents'],
  am: ['home', 'training', 'evaluation', 'levelup', 'kpi', 'documents'],
  kcs: ['home', 'training', 'evaluation', 'levelup', 'kpi', 'documents'],
  bql: ['home', 'training', 'evaluation', 'levelup', 'kpi', 'documents'],
  trainer: ['home', 'training', 'levelup', 'documents'],
}

export function isMobileRole(role) {
  return MOBILE_ROLES.has((role || '').toLowerCase())
}

export function getMenuForRole(role) {
  const keys = ROLE_MENU[(role || '').toLowerCase()] || ROLE_MENU.trainer
  return keys.map((key) => ({ key, ...MENU_ITEMS[key] }))
}
