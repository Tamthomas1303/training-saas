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
  commission: { label: 'Phụ cấp', icon: '💰', path: '/commission' },
  documents: { label: 'Tài liệu', icon: '📁', path: '/documents' },
  users: { label: 'Người dùng', icon: '🧑‍💼', path: '/users' },
  criteria: { label: 'Tiêu chí', icon: '📝', path: '/criteria' },
  levelup: { label: 'Thăng tiến', icon: '🚀', path: '/levelup' },
  sourcing: { label: 'ĐT nguồn', icon: '🎯', path: '/sourcing' },
  reports: { label: 'Báo cáo', icon: '📧', path: '/reports' },
  coursesAdmin: { label: 'Khóa học', icon: '🎬', path: '/courses-admin' },
  myCourses: { label: 'Khóa học của tôi', icon: '🎬', path: '/my-courses' },
  examBanks: { label: 'Ngân hàng câu hỏi', icon: '🗃️', path: '/exam-banks' },
  examsAdmin: { label: 'Ngân hàng đề thi', icon: '📝', path: '/exams-admin' },
  examSessions: { label: 'Kỳ thi', icon: '🗓️', path: '/exam-sessions' },
  myExams: { label: 'Bài thi của tôi', icon: '📝', path: '/my-exams' },
  examGrading: { label: 'Chấm bài', icon: '🖊️', path: '/exam-grading' },
  probationExamApproval: { label: 'Chờ duyệt thi', icon: '🕒', path: '/probation-exam-approval' },
  certTemplates: { label: 'Mẫu chứng chỉ', icon: '🖼️', path: '/cert-templates' },
  certPrograms: { label: 'Chương trình chứng chỉ', icon: '🏆', path: '/cert-programs' },
  certificates: { label: 'Chứng chỉ đã cấp', icon: '📜', path: '/certificates' },
  myCertificates: { label: 'Chứng chỉ của tôi', icon: '📜', path: '/my-certificates' },
  employee360: { label: 'Hồ sơ 360', icon: '🧭', path: '/employee-360' },
  dashboardConfig: { label: 'Cấu hình Dashboard', icon: '⚙️', path: '/dashboard-config' },
  competencyFramework: { label: 'Khung năng lực', icon: '🕸️', path: '/competency-framework' },
  dashboardOverview: { label: 'Tổng hợp CEO/GĐĐT', icon: '📈', path: '/dashboard-overview' },
}

// Vai tro "toan he thong" -> shell desktop (topbar); con lai -> shell mobile (bottom-nav).
// 'employee' (hoc vien - module Khoa hoc, MVP dot 1) cung dung shell mobile (hoc tren dien
// thoai la chinh).
const MOBILE_ROLES = new Set(['trainer', 'bql', 'am', 'kcs', 'employee'])

// M3 — Card Nesting: các chức năng theo vòng đời đào tạo (nhân sự mới / thăng tiến / nguồn / cấp
// trung) gom vào "Trung tâm" (hub, thẻ cha → thẻ con). Thanh nav phẳng chỉ giữ hub + các mục
// tiện ích toàn cục (dashboard/home, KPI, phụ cấp, tài liệu, người dùng).
export const ROLE_MENU = {
  admin: [
    'hub', 'dashboard', 'kpi', 'commission', 'documents', 'users', 'reports',
    'coursesAdmin', 'examBanks', 'examsAdmin', 'examSessions', 'examGrading', 'certTemplates',
    'certPrograms', 'certificates', 'employee360', 'dashboardConfig', 'competencyFramework',
    'dashboardOverview',
  ],
  om: [
    'hub', 'dashboard', 'kpi', 'commission', 'documents', 'reports',
    'employee360', 'dashboardOverview',
  ],
  bod: ['hub', 'dashboard', 'kpi', 'commission', 'documents', 'employee360', 'dashboardOverview'],
  am: ['hub', 'home', 'kpi', 'documents'],
  kcs: ['hub', 'home', 'kpi', 'documents'],
  bql: ['hub', 'home', 'kpi', 'documents'],
  // Prompt_Fix_DotA_29.08.md muc 5: "Cham bai" chi con Admin + Trainer (nhan su phong dao tao).
  trainer: ['hub', 'home', 'documents', 'probationExamApproval', 'examGrading'],
  // Tai khoan hoc vien (module Khoa hoc/Ky thi/Noi he thong, MVP dot 1-3) - pham vi API chi
  // /api/courses/, /api/exams/, /api/integration/ + /api/auth/me (xem
  // accounts.permissions.EmployeeLearnerScope), nen menu CHI co 3 muc de tranh mo trang khac
  // roi bao loi 403.
  employee: ['myCourses', 'myExams', 'myCertificates'],
}

export function isMobileRole(role) {
  return MOBILE_ROLES.has((role || '').toLowerCase())
}

// Muc 16 Phase 1 phan B (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md) - `overridePaths` (mang cac
// route path duoc BAT, tu RoleMenuConfig - xem AuthContext) la TUY CHON: khong truyen/undefined
// -> giu dung ROLE_MENU hardcode nhu truoc (fallback khi chua cau hinh). Co truyen -> loc theo
// path, cho phep BAT ca muc ngoai ROLE_MENU mac dinh cua vai tro (chi doi HIEN THI, ProtectedRoute
// van la lop chan quyen that su - xem App.jsx).
export function getMenuForRole(role, overridePaths) {
  const keys = ROLE_MENU[(role || '').toLowerCase()] || ROLE_MENU.trainer
  if (!overridePaths) {
    return keys.map((key) => ({ key, ...MENU_ITEMS[key] }))
  }
  const allowed = new Set(overridePaths)
  return Object.entries(MENU_ITEMS)
    .filter(([, item]) => allowed.has(item.path))
    .map(([key, item]) => ({ key, ...item }))
}
