import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
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
import MyExamsPage from './pages/MyExamsPage'
import ExamTakingPage from './pages/ExamTakingPage'
import ExamGradingPage from './pages/ExamGradingPage'
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

// #1: LẦN ĐẦU truy cập hệ thống (mở tab mới / vào lại sau khi đóng) → ép về Dashboard.
// Refresh khi đang làm việc (cùng tab) thì GIỮ trang hiện tại — dùng sessionStorage (sống qua
// refresh trong 1 tab, mất khi đóng tab / mở tab mới). Không đụng các trang công khai (guest).
const PUBLIC_PREFIXES = ['/login', '/council-guest', '/attend', '/event']
function InitialRedirect() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => {
    if (loading || !user) return
    if (sessionStorage.getItem('entered')) return
    sessionStorage.setItem('entered', '1')
    if (PUBLIC_PREFIXES.some((p) => location.pathname.startsWith(p))) return
    navigate('/dashboard', { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading])
  return null
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
        <Routes>
          <Route path="/login" element={<LoginPage />} />
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
            path="/exam-grading"
            element={
              <ProtectedRoute roles={['admin', 'om', 'am', 'kcs', 'bql']}>
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
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
