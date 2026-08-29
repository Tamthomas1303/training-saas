import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import EmployeesPage from './pages/EmployeesPage'
import StudentDetailPage from './pages/StudentDetailPage'
import ChecklistPage from './pages/ChecklistPage'
import TrainingPage from './pages/TrainingPage'
import EvaluationPage from './pages/EvaluationPage'
import KpiPage from './pages/KpiPage'
import CommissionPage from './pages/CommissionPage'
import KpiDashboardPage from './pages/KpiDashboardPage'
import UsersPage from './pages/UsersPage'
import DocumentsPage from './pages/DocumentsPage'
import GuestCouncilPage from './pages/GuestCouncilPage'
import GuestAttendPage from './pages/GuestAttendPage'
import GuestEventPage from './pages/GuestEventPage'
import CriteriaEditorPage from './pages/CriteriaEditorPage'
import LevelUpPage from './pages/LevelUpPage'
import SourcingPage from './pages/SourcingPage'
import HubPage from './pages/HubPage'
import MgmtDevPage from './pages/MgmtDevPage'
import TrainingCatalogPage from './pages/TrainingCatalogPage'
import CompetencyGapPage from './pages/CompetencyGapPage'
import TrainingReportPage from './pages/TrainingReportPage'
import CoursesAdminPage from './pages/CoursesAdminPage'
import CourseEditPage from './pages/CourseEditPage'
import MyCoursesPage from './pages/MyCoursesPage'
import CoursePlayerPage from './pages/CoursePlayerPage'
import ExamBanksAdminPage from './pages/ExamBanksAdminPage'
import ExamBankEditPage from './pages/ExamBankEditPage'
import ExamsAdminPage from './pages/ExamsAdminPage'
import ExamEditPage from './pages/ExamEditPage'
import ExamSessionsPage from './pages/ExamSessionsPage'
import MyExamsPage from './pages/MyExamsPage'
import ExamTakingPage from './pages/ExamTakingPage'
import ExamGradingPage from './pages/ExamGradingPage'
import CertTemplatesAdminPage from './pages/CertTemplatesAdminPage'
import CertProgramsAdminPage from './pages/CertProgramsAdminPage'
import CertificatesAdminPage from './pages/CertificatesAdminPage'
import MyCertificatesPage from './pages/MyCertificatesPage'
import Employee360Page from './pages/Employee360Page'
import SettingsPage from './pages/SettingsPage'
import ErrorBoundary from './components/ErrorBoundary'
import ForcedPasswordChangeGate from './components/ForcedPasswordChangeGate'
import InstallAppBanner from './components/InstallAppBanner'
import CompetencyFrameworkAdminPage from './pages/CompetencyFrameworkAdminPage'
import DashboardOverviewPage from './pages/DashboardOverviewPage'
import AutomationPage from './pages/AutomationPage'
import ProbationExamApprovalPage from './pages/ProbationExamApprovalPage'
import SetPasswordPage from './pages/SetPasswordPage'
import api from './api/client'
import { isMobileRole } from './config/menu'
import { flushQueue, initOfflineSync } from './utils/offlineQueue'

function HomeRouter() {
  const { user } = useAuth()
  // Tai khoan hoc vien (module Khoa hoc, MVP dot 1) khong goi duoc /employees/home/ (pham vi API
  // chi /api/courses/ - xem accounts.permissions.EmployeeLearnerScope) nen vao thang "Khoa hoc
  // cua toi" thay vi man Trang chu danh cho nhan vien BQL/Trainer/AM/KCS.
  if ((user.role || '').toLowerCase() === 'employee') {
    return <MyCoursesPage />
  }
  return isMobileRole(user.role) ? <HomePage /> : <DashboardPage />
}

// #1 (sua o Prompt_Fix_DotA_29.08.md muc 2): LAN DAU truy cap he thong (mo tab moi / vao lai sau
// khi dong) -> ep ve [Trang chu] ('/'), KHONG phai Dashboard ('/dashboard' - van con nguyen
// trong nhom [Quan ly bao cao], chi khong con la trang mac dinh sau dang nhap).
// Refresh khi đang làm việc (cùng tab) thì GIỮ trang hiện tại — dùng sessionStorage (sống qua
// refresh trong 1 tab, mất khi đóng tab / mở tab mới). Không đụng các trang công khai (guest).
const PUBLIC_PREFIXES = ['/login', '/council-guest', '/attend', '/event', '/set-password']
function InitialRedirect() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => {
    if (loading || !user) return
    if (sessionStorage.getItem('entered')) return
    sessionStorage.setItem('entered', '1')
    if (PUBLIC_PREFIXES.some((p) => location.pathname.startsWith(p))) return
    navigate('/', { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading])
  return null
}

// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 4) - banner cai app CHI hien cho tai khoan da dang nhap
// (khong hien tren /login hay cac trang khach cong khai).
function InstallAppBannerGate() {
  const { user } = useAuth()
  if (!user) return null
  return <InstallAppBanner />
}

function App() {
  useEffect(() => {
    initOfflineSync(api)
    flushQueue(api)
  }, [])

  return (
    <BrowserRouter>
      <AuthProvider>
        <InitialRedirect />
        <ForcedPasswordChangeGate />
        <InstallAppBannerGate />
        {/* Luoi an toan cuoi cung (Phan 1, Prompt_Fix_TrangTrang_MapUndefined.md) - cho cac
            route CONG KHAI khong qua ProtectedRoute (login/guest/set-password), la noi da co
            boundary rieng theo tung route (xem ProtectedRoute.jsx). */}
        <ErrorBoundary>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/set-password" element={<SetPasswordPage />} />
          <Route path="/council-guest/:token" element={<GuestCouncilPage />} />
          <Route path="/attend/:token" element={<GuestAttendPage />} />
          <Route path="/event/:token" element={<GuestEventPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <HomeRouter />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <HomeRouter />
              </ProtectedRoute>
            }
          />
          <Route
            path="/employees"
            element={
              <ProtectedRoute>
                <EmployeesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/employees/:id"
            element={
              <ProtectedRoute>
                <StudentDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/checklist"
            element={
              <ProtectedRoute>
                <ChecklistPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/training"
            element={
              <ProtectedRoute>
                <TrainingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/evaluation"
            element={
              <ProtectedRoute>
                <EvaluationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/kpi"
            element={
              <ProtectedRoute>
                <KpiPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/commission"
            element={
              <ProtectedRoute>
                <CommissionPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/kpi-dashboard"
            element={
              <ProtectedRoute>
                <KpiDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/documents"
            element={
              <ProtectedRoute>
                <DocumentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/users"
            element={
              <ProtectedRoute roles={['admin']}>
                <UsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/criteria"
            element={
              <ProtectedRoute roles={['admin', 'om']}>
                <CriteriaEditorPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/levelup"
            element={
              <ProtectedRoute roles={['admin', 'om', 'bql', 'am', 'kcs', 'trainer']}>
                <LevelUpPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/sourcing"
            element={
              <ProtectedRoute roles={['admin', 'om', 'bql', 'trainer']}>
                <SourcingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/mgmt-development"
            element={
              <ProtectedRoute roles={['admin', 'om', 'bod']}>
                <MgmtDevPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/training-catalog"
            element={
              <ProtectedRoute roles={['admin', 'om']}>
                <TrainingCatalogPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competency-gap"
            element={
              <ProtectedRoute roles={['admin', 'om', 'am', 'kcs', 'bql', 'trainer']}>
                <CompetencyGapPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute roles={['admin', 'om']}>
                <TrainingReportPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/hub"
            element={
              <ProtectedRoute>
                <HubPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses-admin"
            element={
              <ProtectedRoute roles={['admin']}>
                <CoursesAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses-admin/:id"
            element={
              <ProtectedRoute roles={['admin']}>
                <CourseEditPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-courses"
            element={
              <ProtectedRoute>
                <MyCoursesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-courses/:courseId"
            element={
              <ProtectedRoute>
                <CoursePlayerPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exam-banks"
            element={
              <ProtectedRoute roles={['admin']}>
                <ExamBanksAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exam-banks/:id"
            element={
              <ProtectedRoute roles={['admin']}>
                <ExamBankEditPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exams-admin"
            element={
              <ProtectedRoute roles={['admin']}>
                <ExamsAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exams-admin/:id"
            element={
              <ProtectedRoute roles={['admin']}>
                <ExamEditPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exam-sessions"
            element={
              <ProtectedRoute roles={['admin']}>
                <ExamSessionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exam-grading"
            element={
              // Prompt_Fix_DotA_29.08.md muc 5: chi con Admin + Trainer (phong dao tao).
              <ProtectedRoute roles={['admin', 'trainer']}>
                <ExamGradingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-exams"
            element={
              <ProtectedRoute>
                <MyExamsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-exams/attempt/:attemptId"
            element={
              <ProtectedRoute>
                <ExamTakingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cert-templates"
            element={
              <ProtectedRoute roles={['admin']}>
                <CertTemplatesAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cert-programs"
            element={
              <ProtectedRoute roles={['admin']}>
                <CertProgramsAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/certificates"
            element={
              <ProtectedRoute roles={['admin']}>
                <CertificatesAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-certificates"
            element={
              <ProtectedRoute>
                <MyCertificatesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee-360"
            element={
              <ProtectedRoute roles={['admin', 'om', 'bod']}>
                <Employee360Page />
              </ProtectedRoute>
            }
          />
          {/* UI dot 3 (Prompt_UI_Dot3_CaiDat_GradingConfig.md muc A): "Cau hinh Dashboard" doi
              vao the trong /settings - giu route cu song duoi dang redirect de link/bookmark cu
              khong gay loi. */}
          <Route path="/dashboard-config" element={<Navigate to="/settings?tab=dashboard" replace />} />
          <Route
            path="/settings"
            element={
              <ProtectedRoute roles={['admin']}>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competency-framework"
            element={
              <ProtectedRoute roles={['admin']}>
                <CompetencyFrameworkAdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard-overview"
            element={
              <ProtectedRoute roles={['admin', 'om', 'bod']}>
                <DashboardOverviewPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/automation"
            element={
              <ProtectedRoute roles={['admin']}>
                <AutomationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/probation-exam-approval"
            element={
              <ProtectedRoute roles={['admin', 'trainer']}>
                <ProbationExamApprovalPage />
              </ProtectedRoute>
            }
          />
        </Routes>
        </ErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
