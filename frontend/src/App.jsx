import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
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
import CriteriaEditorPage from './pages/CriteriaEditorPage'
import api from './api/client'
import { isMobileRole } from './config/menu'
import { flushQueue, initOfflineSync } from './utils/offlineQueue'

function HomeRouter() {
  const { user } = useAuth()
  return isMobileRole(user.role) ? <HomePage /> : <DashboardPage />
}

function App() {
  useEffect(() => {
    initOfflineSync(api)
    flushQueue(api)
  }, [])

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/council-guest/:token" element={<GuestCouncilPage />} />
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
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
