// M3 — Card Nesting: 4 miền cha của phòng Đào tạo → thẻ con (parent-child). Dùng cho HubPage.
// Mỗi thẻ con có `roles` để lọc theo vai trò; ProtectedRoute vẫn là lớp chặn thật ở route.
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
      { label: 'Chương trình & Đợt đào tạo', path: '/sourcing?audience=management', icon: '🎓', roles: ['admin', 'om', 'bql', 'trainer'] },
      { label: 'Danh mục nội dung đào tạo', path: '/training-catalog', icon: '🗂️', roles: ['admin', 'om'] },
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
