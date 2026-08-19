// M3 — Card Nesting: 4 miền cha của phòng Đào tạo → thẻ con (parent-child). Dùng cho HubPage.
// Mỗi thẻ con có `roles` để lọc theo vai trò; ProtectedRoute vẫn là lớp chặn thật ở route.
// `group` (tùy chọn) hiện tiêu đề nhóm nhỏ NGAY TRƯỚC thẻ con đó khi giá trị group đổi so với
// thẻ liền trước (xem HubPage) - dùng để gom cụm "Ngân hàng câu hỏi/đề thi" (Nội dung) tách
// khỏi "Kỳ thi" (Tổ chức đào tạo) kiểu CLS (Prompt_NganHangDe_va_KyThi_kieuCLS.md muc 4), KHÔNG
// đổi path/roles của các mục khác trong domain này.
export const DOMAINS = [
  {
    key: 'new',
    title: 'Nhân sự mới',
    icon: '👤',
    desc: 'Onboarding: hồ sơ, checklist, đào tạo tại điểm, đánh giá thử việc.',
    children: [
      { label: 'Danh sách nhân sự mới', path: '/employees', icon: '👥', roles: ['admin', 'om', 'bod'] },
      { label: 'Đào tạo tại điểm', path: '/training', icon: '🎓', roles: ['admin', 'om', 'bql', 'trainer', 'am', 'kcs'] },
      { label: 'Đánh giá', path: '/evaluation', icon: '✅', roles: ['admin', 'om', 'bql', 'am', 'kcs'] },
      { label: 'Checklist đào tạo', path: '/checklist', icon: '📋', roles: ['admin', 'om', 'bod'] },
      { label: 'Tiêu chí đánh giá', path: '/criteria', icon: '📝', roles: ['admin', 'om'] },
      { label: 'Khóa học trực tuyến', path: '/courses-admin', icon: '🎬', roles: ['admin'] },
      { label: 'Ngân hàng câu hỏi', path: '/exam-banks', icon: '🗃️', roles: ['admin'], group: 'Nội dung' },
      { label: 'Ngân hàng đề thi', path: '/exams-admin', icon: '📝', roles: ['admin'], group: 'Nội dung' },
      { label: 'Kỳ thi', path: '/exam-sessions', icon: '🗓️', roles: ['admin'], group: 'Tổ chức đào tạo' },
      {
        label: 'Chấm bài', path: '/exam-grading', icon: '🖊️', roles: ['admin', 'om', 'am', 'kcs', 'bql'],
        group: 'Tổ chức đào tạo',
      },
      { label: 'Mẫu chứng chỉ', path: '/cert-templates', icon: '🖼️', roles: ['admin'] },
      { label: 'Chương trình chứng chỉ', path: '/cert-programs', icon: '🏆', roles: ['admin'] },
      { label: 'Chứng chỉ đã cấp', path: '/certificates', icon: '📜', roles: ['admin'] },
    ],
  },
  {
    key: 'levelup',
    title: 'Thăng tiến',
    icon: '🚀',
    desc: 'Lộ trình lên level theo vị trí: theo dõi, đăng ký, đào tạo, đánh giá, lên bậc.',
    children: [
      { label: 'Lộ trình thăng tiến', path: '/levelup', icon: '🚀', roles: ['admin', 'om', 'bql', 'am', 'kcs', 'trainer'] },
    ],
  },
  {
    key: 'source',
    title: 'Nhân sự nguồn (Ban quản lý)',
    icon: '🎯',
    desc: 'Đào tạo Ban quản lý: Bếp phó, Bếp trưởng, Giám sát, Quản lý nhà hàng (offline + đánh giá).',
    children: [
      { label: 'Danh sách nhân sự nguồn', path: '/levelup', icon: '🏅', roles: ['admin', 'om'] },
      { label: 'Ban quản lý — Đào tạo & Đánh giá', path: '/mgmt-development', icon: '📋', roles: ['admin', 'om', 'bod'] },
      { label: 'Chương trình, Đợt & Nội dung', path: '/sourcing?audience=management', icon: '🎓', roles: ['admin', 'om', 'bql', 'trainer'] },
      { label: 'Lập danh sách theo khung năng lực', path: '/competency-gap', icon: '🔎', roles: ['admin', 'om', 'am', 'kcs', 'bql', 'trainer'] },
    ],
  },
  {
    key: 'mid',
    title: 'Cấp trung (AM / KCS)',
    icon: '🏛️',
    desc: 'Đào tạo quản lý cấp trung: AM (Quản lý vùng), KCS (Giám sát bếp hệ thống), Quản lý vận hành.',
    children: [
      { label: 'Chương trình & Đợt (cấp trung)', path: '/sourcing?audience=middle', icon: '🏛️', roles: ['admin', 'om'] },
    ],
  },
]

export function visibleChildren(domain, role) {
  const r = (role || '').toLowerCase()
  return (domain.children || []).filter((c) => c.roles.includes(r))
}
