// Dieu huong console admin - UI dot 2 (Prompt_UI_Dot2_ConsoleAdmin.md muc A). CHI danh cho
// role admin/om/bod tren desktop (xem components/Sidebar.jsx + AppShell.jsx) - KHONG dung cho
// mobile role (ho van dung config/menu.js + BottomNav nhu cu).
//
// Moi item la 1 ROUTE DA TON TAI (khong tao route moi, chi nhom lai dung bang 8 nhom trong
// prompt). `roles` = giao cua roles that su cua route do (xem App.jsx::ProtectedRoute) voi tap
// {admin, om, bod} - dam bao sidebar KHONG hien muc ngoai quyen (dung y "loc nhu getMenuForRole").
//
// Ghi chu pham vi dot 2: "Vi tri chuc danh"/"Co cau to chuc" (nhom 1) va "Cai dat"/"Lich su he
// thong" (nhom 8) CHUA co route - de danh cho dot 3, khong dua vao day. "/commission" (Phu cap)
// khong co trong bang 8 nhom cua prompt goc nen CHUA dua vao sidebar moi (da bao lai voi anh
// Chung trong bao cao) - van vao duoc qua URL truc tiep, chi khong co lien ket nhanh.
import {
  Award,
  BarChart3,
  Building2,
  CalendarCheck,
  ClipboardCheck,
  ClipboardList,
  Compass,
  Database,
  FileBadge,
  FileText,
  FolderOpen,
  GraduationCap,
  Home,
  IdCard,
  Layers,
  LayoutDashboard,
  Network,
  PencilLine,
  ScrollText,
  Settings,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react'

const ALL = ['admin', 'om', 'bod']

export const ADMIN_NAV = [
  {
    key: 'home',
    title: 'Trang chủ',
    icon: Home,
    path: '/', // nhom don, khong co items con - bam thang vao Dashboard
    roles: ALL,
  },
  {
    key: 'org',
    title: 'Quản lý tổ chức',
    icon: Building2,
    items: [
      { label: 'Người dùng', path: '/users', icon: Users, roles: ['admin'] },
      { label: 'Mẫu chứng chỉ', path: '/cert-templates', icon: FileBadge, roles: ['admin'] },
      { label: 'Chứng chỉ đã cấp', path: '/certificates', icon: Award, roles: ['admin'] },
      { label: 'Chương trình chứng chỉ', path: '/cert-programs', icon: ScrollText, roles: ['admin'] },
    ],
  },
  {
    key: 'training-mgmt',
    title: 'Quản lý đào tạo',
    icon: GraduationCap,
    items: [
      { label: 'Danh sách nhân sự', path: '/employees', icon: Users, roles: ALL },
      { label: 'Checklist đào tạo', path: '/checklist', icon: ClipboardCheck, roles: ALL },
      { label: 'Checklist đánh giá (tiêu chí)', path: '/criteria', icon: ClipboardList, roles: ['admin', 'om'] },
      { label: 'Tài liệu đào tạo', path: '/documents', icon: FolderOpen, roles: ALL },
    ],
  },
  {
    key: 'training-org',
    title: 'Tổ chức đào tạo',
    icon: CalendarCheck,
    items: [
      { label: 'Khóa học', path: '/courses-admin', icon: GraduationCap, roles: ['admin'] },
      { label: 'Kỳ thi', path: '/exam-sessions', icon: CalendarCheck, roles: ['admin'] },
      { label: 'Chấm bài', path: '/exam-grading', icon: PencilLine, roles: ['admin', 'om'] },
    ],
  },
  {
    key: 'content',
    title: 'Quản lý nội dung',
    icon: Layers,
    items: [
      { label: 'Ngân hàng câu hỏi', path: '/exam-banks', icon: Database, roles: ['admin'] },
      { label: 'Ngân hàng đề thi', path: '/exams-admin', icon: FileText, roles: ['admin'] },
    ],
  },
  {
    key: 'reports',
    title: 'Quản lý báo cáo',
    icon: BarChart3,
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, roles: ALL },
      { label: 'KPI Đào tạo', path: '/kpi', icon: TrendingUp, roles: ALL },
      { label: 'Thống kê KPI', path: '/kpi-dashboard', icon: BarChart3, roles: ALL },
      { label: 'Báo cáo', path: '/reports', icon: FileText, roles: ['admin', 'om'] },
      { label: 'Tổng hợp CEO/GĐĐT', path: '/dashboard-overview', icon: BarChart3, roles: ALL },
    ],
  },
  {
    key: 'competency',
    title: 'Quản lý năng lực',
    icon: Network,
    items: [
      { label: 'Hồ sơ 360', path: '/employee-360', icon: IdCard, roles: ALL },
      { label: 'Khung năng lực', path: '/competency-framework', icon: Network, roles: ['admin'] },
    ],
  },
  {
    key: 'hub',
    title: 'Trung tâm đào tạo',
    icon: Compass,
    items: [
      { label: 'Trung tâm đào tạo', path: '/hub', icon: Compass, roles: ALL },
      { label: 'Lộ trình thăng tiến', path: '/levelup', icon: TrendingUp, roles: ['admin', 'om'] },
      { label: 'ĐT nguồn', path: '/sourcing', icon: Target, roles: ['admin', 'om'] },
    ],
  },
  {
    key: 'system',
    title: 'Quản lý hệ thống',
    icon: Settings,
    items: [
      { label: 'Cấu hình Dashboard', path: '/dashboard-config', icon: Settings, roles: ['admin'] },
    ],
  },
]
