import { Navigate, useLocation } from 'react-router-dom'
import ErrorBoundary from '../components/ErrorBoundary'
import { useAuth } from './AuthContext'

// Prompt_Fix_TrangTrang_MapUndefined.md (Phan 1) - ErrorBoundary boc O DAY (khong phai trong
// AppShell) vi cac trang trong app nay TU GOI <AppShell> ben trong ham render cua chinh no (vd
// return <AppShell>{...noi dung...}</AppShell>) - loi .map/render xay ra TRONG luc React thuc
// thi ham cua trang do, tuc la TRUOC/BEN NGOAI AppShell trong cay component, nen 1 boundary dat
// BEN TRONG AppShell se khong bao gio bat duoc loi nay. Dat o ProtectedRoute (bao MOI trang da
// dang nhap, moi route la 1 instance rieng) la diem duy nhat vua la TO TIEN thuc su cua component
// trang, vua reset trang thai loi tu nhien khi chuyen route (Route khac = element/instance moi).
export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <p>Đang tải...</p>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (roles && !roles.includes(user.role)) {
    return <p>Bạn không có quyền truy cập trang này.</p>
  }

  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>
}
