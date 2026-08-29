import { createContext, useContext, useEffect, useState } from 'react'
import api from '../api/client'
import { applyBrand } from '../utils/color'

const AuthContext = createContext(null)

// UI dot 1 (Prompt_UI_Dot1_Theme.md muc 3c): sau khi biet user (dang nhap hoac /auth/me/ luc
// mo lai app), goi 1 LAN de lay mau/ten/logo thuong hieu cua tenant, ghi bien CSS --brand* +
// luu vao state 'brand' de TopBar/mobile-topstrip doc ten/logo. Loi mang -> bo qua am tham,
// giu mac dinh CSS tinh trong theme.css (khong chan dang nhap).
function loadBrand(setBrand) {
  api.get('/settings/brand/')
    .then(({ data }) => {
      applyBrand(data.brand_hex)
      setBrand(data)
    })
    .catch(() => {})
}

// Muc 16 Phase 1 phan B (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md) - tai {role: [path bat,...]}
// CHI cho cac vai tro DA duoc Admin cau hinh rieng; vai tro vang mat = "chua cau hinh", cac noi
// doc (AppShell/Sidebar/config/menu.js) tu fallback ve mac dinh hardcode hien hanh, KHONG doi
// hanh vi. Tai khoan hoc vien (role='employee') co pham vi API rieng (xem accounts.permissions.
// EmployeeLearnerScope) - khong goi duoc endpoint nay, menu cua ho la danh sach co dinh.
function loadRoleMenuConfig(role, setRoleMenuConfig) {
  if ((role || '').toLowerCase() === 'employee') {
    setRoleMenuConfig({})
    return
  }
  api.get('/settings/role-menu/')
    .then(({ data }) => setRoleMenuConfig(data || {}))
    .catch(() => setRoleMenuConfig({}))
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [brand, setBrand] = useState(null)
  const [roleMenuConfig, setRoleMenuConfig] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setLoading(false)
      return
    }
    api
      .get('/auth/me/')
      .then(({ data }) => {
        setUser(data)
        loadBrand(setBrand)
        loadRoleMenuConfig(data.role, setRoleMenuConfig)
      })
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      })
      .finally(() => setLoading(false))
  }, [])

  async function login(username, password) {
    const { data } = await api.post('/auth/login/', { username, password })
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    setUser(data.user)
    loadBrand(setBrand)
    loadRoleMenuConfig(data.user.role, setRoleMenuConfig)
    return data.user
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{ user, brand, roleMenuConfig, loading, login, logout, setUser, setBrand, setRoleMenuConfig }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
