// Ban do menu theo vai tro - port tinh than Code.gs::_menusForRole (03_THIET_KE_GIAO_DIEN.md
// muc 3-4), anh xa sang cac trang thuc te da dung trong he thong nay (chua co man Documents/
// Users rieng nen tam khong dua vao menu - se bo sung o dot sau).
export const MENU_ITEMS = {
  home: { label: 'Trang chủ', icon: '🏠', path: '/' },
  restaurants: { label: 'Nhà hàng', icon: '🏬', path: '/restaurants' },
  students: { label: 'Nhân sự', icon: '👥', path: '/employees' },
  checklist: { label: 'Checklist', icon: '📋', path: '/checklist' },
  training: { label: 'Đào tạo', icon: '🎓', path: '/training' },
  evaluation: { label: 'Đánh giá', icon: '✅', path: '/evaluation' },
  kpi: { label: 'KPI', icon: '📈', path: '/kpi' },
  kpiDashboard: { label: 'Thống kê KPI', icon: '📊', path: '/kpi-dashboard' },
  commission: { label: 'Phụ cấp', icon: '💰', path: '/commission' },
}

// Vai tro "toan he thong" -> shell desktop (topbar); con lai -> shell mobile (bottom-nav).
const MOBILE_ROLES = new Set(['trainer', 'bql', 'am', 'kcs'])

const ROLE_MENU = {
  admin: ['home', 'students', 'restaurants', 'checklist', 'kpi', 'kpiDashboard', 'commission'],
  om: ['home', 'students', 'restaurants', 'checklist', 'kpi', 'kpiDashboard', 'commission'],
  bod: ['home', 'students', 'restaurants', 'checklist', 'kpi', 'kpiDashboard', 'commission'],
  am: ['home', 'evaluation', 'kpi'],
  kcs: ['home', 'evaluation', 'kpi'],
  bql: ['home', 'training', 'evaluation', 'kpi'],
  trainer: ['home', 'training'],
}

export function isMobileRole(role) {
  return MOBILE_ROLES.has((role || '').toLowerCase())
}

export function getMenuForRole(role) {
  const keys = ROLE_MENU[(role || '').toLowerCase()] || ROLE_MENU.trainer
  return keys.map((key) => ({ key, ...MENU_ITEMS[key] }))
}
