import { useEffect, useRef, useState } from 'react'
import { MoreVertical } from 'lucide-react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Pager from '../components/Pager'
import RestaurantsPanel from '../components/RestaurantsPanel'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'om', label: 'OM' },
  { value: 'bod', label: 'BOD' },
  { value: 'am', label: 'AM' },
  { value: 'kcs', label: 'KCS' },
  { value: 'bql', label: 'BQL' },
  { value: 'trainer', label: 'Trainer' },
]

const JOB_TITLE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'qlnh', label: 'Quản lý nhà hàng' },
  { value: 'giam_sat', label: 'Giám sát' },
  { value: 'bep_truong', label: 'Bếp trưởng' },
  { value: 'bep_pho', label: 'Bếp phó' },
]

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'locked', label: 'Locked' },
]

const STATUS_VARIANTS = { active: 'success', inactive: 'neutral', locked: 'danger' }

const EMPTY_FORM = {
  id: null, username: '', password: '', full_name: '', role: 'trainer', job_title: '',
  restaurant: '', trainer_zone: '', status: 'active',
}

// Nhom 1 muc C (Prompt_Nhom1_NhanSu_NguoiDung.md) - menu "3 cham" moi dong: Sua thong tin /
// Cap nhat trang thai (nhanh, khong mo modal Sua day du) / Dat lai mat khau. Muc D them Luu
// tru/Khoi phuc + Xoa cung. Dung pattern click-outside giong components/UserMenu.jsx.
function RowActionsMenu({ user: u, onEdit, onStatus, onResetPassword, onArchive, onRestore, onHardDelete }) {
  const [open, setOpen] = useState(false)
  const [statusSubmenu, setStatusSubmenu] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
        setStatusSubmenu(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function pick(fn) {
    return () => {
      setOpen(false)
      setStatusSubmenu(false)
      fn()
    }
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        className="btn-outline btn-sm"
        title="Thao tác khác"
        onClick={() => setOpen((v) => !v)}
        style={{ display: 'inline-flex', alignItems: 'center', padding: '4px 8px' }}
      >
        <MoreVertical size={14} />
      </button>
      {open && (
        <div className="user-menu-popup" style={{ minWidth: 210, zIndex: 50 }}>
          <button className="user-menu-item" onClick={pick(onEdit)}>Sửa thông tin</button>
          {!u.archived_at && (
            <button className="user-menu-item" onClick={() => setStatusSubmenu((v) => !v)}>
              Cập nhật trạng thái ▾
            </button>
          )}
          {statusSubmenu && (
            <div style={{ paddingLeft: 12, display: 'flex', flexDirection: 'column' }}>
              {STATUS_OPTIONS.map((o) => (
                <button
                  key={o.value} className="user-menu-item"
                  style={{ fontSize: 13, opacity: u.status === o.value ? 0.5 : 1 }}
                  disabled={u.status === o.value}
                  onClick={pick(() => onStatus(o.value))}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}
          {!u.archived_at && (
            <button className="user-menu-item" onClick={pick(onResetPassword)}>Đặt lại mật khẩu</button>
          )}
          {u.archived_at ? (
            <button className="user-menu-item" onClick={pick(onRestore)}>Khôi phục</button>
          ) : (
            <button className="user-menu-item" onClick={pick(onArchive)}>Lưu trữ</button>
          )}
          <button className="user-menu-item" style={{ color: 'var(--danger)' }} onClick={pick(onHardDelete)}>
            Xóa cứng...
          </button>
        </div>
      )}
    </div>
  )
}

export default function UsersPage() {
  const [tab, setTab] = useState('users')
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [areaUser, setAreaUser] = useState(null)
  const [areaSelected, setAreaSelected] = useState([])
  const [areaSaving, setAreaSaving] = useState(false)

  // Nhom 1 muc D.1 - mac dinh AN tai khoan da luu tru, bat cong tac de xem lai + khoi phuc.
  const [showArchived, setShowArchived] = useState(false)
  // Nhom 1 muc C.3 - ket qua reset mat khau (hien 1 LAN duy nhat cho Admin copy).
  const [resetResult, setResetResult] = useState(null)
  const [actionMsg, setActionMsg] = useState('')
  // Nhom 1 muc D.2 - xoa cung: xac nhan kep bang go lai username.
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [deleting, setDeleting] = useState(false)
  // Prompt_Fix_DotA_29.08.md muc 6 (#17a) - chon nhieu dong -> Luu tru/Xoa cac muc da chon.
  const [selectedIds, setSelectedIds] = useState([])
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [bulkDeleteConfirmText, setBulkDeleteConfirmText] = useState('')
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkResultMsg, setBulkResultMsg] = useState('')

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })

  const params = {
    search, role: role || undefined, archived: showArchived ? 'true' : undefined,
    page, page_size: PAGE_SIZE, refreshKey,
  }
  const { data, loading, error } = usePaginatedList('/auth/users/', params)

  useEffect(() => {
    setSelectedIds([])
  }, [search, role, page, showArchived, refreshKey])

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  function openCreate() {
    setForm({ ...EMPTY_FORM })
    setFormError('')
  }

  function openEdit(u) {
    setForm({
      id: u.id, username: u.username, password: '', full_name: u.full_name, role: u.role,
      job_title: u.job_title || '', restaurant: u.restaurant || '', trainer_zone: u.trainer_zone || '',
      status: u.status,
    })
    setFormError('')
  }

  async function saveForm() {
    setSaving(true)
    setFormError('')
    const payload = {
      username: form.username, full_name: form.full_name, role: form.role,
      job_title: form.job_title || null, restaurant: form.restaurant || null,
      trainer_zone: form.trainer_zone, status: form.status,
    }
    if (form.password) payload.password = form.password
    try {
      if (form.id) {
        await api.patch(`/auth/users/${form.id}/`, payload)
      } else {
        await api.post('/auth/users/', payload)
      }
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được người dùng.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function openAreas(u) {
    setAreaUser(u)
    try {
      const { data } = await api.get(`/auth/users/${u.id}/areas/`)
      setAreaSelected(data.restaurant_ids)
    } catch {
      setAreaSelected([])
    }
  }

  function toggleArea(id) {
    setAreaSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function saveAreas() {
    setAreaSaving(true)
    try {
      await api.post(`/auth/users/${areaUser.id}/areas/`, { restaurant_ids: areaSelected })
      setAreaUser(null)
    } catch {
      // giu popup mo de thu lai
    } finally {
      setAreaSaving(false)
    }
  }

  async function updateStatus(u, status) {
    setActionMsg('')
    try {
      await api.patch(`/auth/users/${u.id}/`, { status })
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setActionMsg(err.response?.data?.detail || 'Không đổi được trạng thái.')
    }
  }

  async function resetPassword(u) {
    setActionMsg('')
    try {
      const { data } = await api.post(`/auth/users/${u.id}/reset-password/`)
      setResetResult(data)
    } catch (err) {
      setActionMsg(err.response?.data?.detail || 'Không đặt lại được mật khẩu.')
    }
  }

  async function archiveUser(u) {
    setActionMsg('')
    try {
      await api.post(`/auth/users/${u.id}/archive/`)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setActionMsg(err.response?.data?.detail || 'Không lưu trữ được tài khoản.')
    }
  }

  async function restoreUser(u) {
    setActionMsg('')
    try {
      await api.post(`/auth/users/${u.id}/restore/`)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setActionMsg(err.response?.data?.detail || 'Không khôi phục được tài khoản.')
    }
  }

  function openHardDelete(u) {
    setDeleteTarget(u)
    setDeleteConfirmText('')
    setDeleteError('')
  }

  async function confirmHardDelete() {
    setDeleting(true)
    setDeleteError('')
    try {
      await api.delete(`/auth/users/${deleteTarget.id}/`, { data: { confirm_username: deleteConfirmText } })
      setDeleteTarget(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setDeleteError(err.response?.data?.detail || 'Không xóa được tài khoản.')
    } finally {
      setDeleting(false)
    }
  }

  function toggleSelectOne(id) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  function toggleSelectAll() {
    const pageIds = data.results.map((u) => u.id)
    const allSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.includes(id))
    setSelectedIds(allSelected ? [] : pageIds)
  }

  const selectedUsers = data.results.filter((u) => selectedIds.includes(u.id))

  async function bulkArchiveSelected() {
    setBulkBusy(true)
    setBulkResultMsg('')
    let ok = 0
    for (const u of selectedUsers.filter((x) => !x.archived_at)) {
      try {
        await api.post(`/auth/users/${u.id}/archive/`)
        ok += 1
      } catch {
        // bo qua, van tiep tuc voi cac tai khoan con lai
      }
    }
    setBulkBusy(false)
    setBulkResultMsg(`Đã lưu trữ ${ok}/${selectedUsers.length} tài khoản.`)
    setSelectedIds([])
    setRefreshKey((k) => k + 1)
  }

  function openBulkDelete() {
    setBulkDeleteConfirmText('')
    setBulkResultMsg('')
    setBulkDeleteOpen(true)
  }

  async function confirmBulkDelete() {
    setBulkBusy(true)
    let ok = 0
    const failReasons = []
    for (const u of selectedUsers) {
      try {
        await api.delete(`/auth/users/${u.id}/`, { data: { confirm_username: u.username } })
        ok += 1
      } catch (err) {
        failReasons.push(`${u.username}: ${err.response?.data?.detail || 'lỗi không xác định'}`)
      }
    }
    setBulkBusy(false)
    setBulkDeleteOpen(false)
    setBulkResultMsg(
      ok === selectedUsers.length
        ? `Đã xóa cứng ${ok}/${selectedUsers.length} tài khoản.`
        : `Đã xóa ${ok}/${selectedUsers.length} tài khoản. Bị chặn: ${failReasons.join(' | ')}`
    )
    setSelectedIds([])
    setRefreshKey((k) => k + 1)
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button className={`btn-sm ${tab === 'users' ? '' : 'btn-outline'}`} onClick={() => setTab('users')}>
          Người dùng
        </button>
        <button className={`btn-sm ${tab === 'restaurants' ? '' : 'btn-outline'}`} onClick={() => setTab('restaurants')}>
          Nhà hàng
        </button>
      </div>

      {tab === 'restaurants' && <RestaurantsPanel />}

      {tab === 'users' && (
      <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Người dùng</h2>
        <button onClick={openCreate}>+ Thêm người dùng</button>
      </div>

      <FilterBar>
        <input
          style={s.input}
          placeholder="Tìm theo tài khoản / họ tên..."
          value={search}
          onChange={onFilterChange(setSearch)}
        />
        <select style={s.select} value={role} onChange={onFilterChange(setRole)}>
          <option value="">Tất cả vai trò</option>
          {ROLE_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <button
          className={`btn-sm ${showArchived ? '' : 'btn-outline'}`}
          onClick={() => { setShowArchived((v) => !v); setPage(1) }}
        >
          {showArchived ? 'Đang xem: đã lưu trữ' : 'Hiện tài khoản đã lưu trữ'}
        </button>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {actionMsg && <p style={{ color: 'var(--danger)' }}>{actionMsg}</p>}
      {bulkResultMsg && <p className="muted-note">{bulkResultMsg}</p>}

      {selectedIds.length > 0 && (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 10, margin: '8px 0', padding: '8px 12px',
            background: 'var(--brand-soft)', borderRadius: 8,
          }}
        >
          <span>Đã chọn {selectedIds.length} tài khoản</span>
          <button className="btn-outline btn-sm" onClick={bulkArchiveSelected} disabled={bulkBusy}>
            Lưu trữ đã chọn
          </button>
          <button className="btn-sm btn-danger" onClick={openBulkDelete} disabled={bulkBusy}>
            Xóa các mục đã chọn
          </button>
          <button className="btn-outline btn-sm" onClick={() => setSelectedIds([])} disabled={bulkBusy}>
            Bỏ chọn
          </button>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="table-sticky">
          <Table>
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    checked={data.results.length > 0 && data.results.every((u) => selectedIds.includes(u.id))}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>Tài khoản</th>
                <th>Họ tên</th>
                <th>Vai trò</th>
                <th>Nhà hàng / Phòng ban</th>
                <th>Vị trí làm việc</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((u) => (
                <tr key={u.id}>
                  <td>
                    <input type="checkbox" checked={selectedIds.includes(u.id)} onChange={() => toggleSelectOne(u.id)} />
                  </td>
                  <td>{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>{u.role}</td>
                  <td>{u.restaurant_name}</td>
                  <td>{u.position}</td>
                  <td>
                    <Badge variant={STATUS_VARIANTS[u.status] || 'neutral'}>{u.status}</Badge>
                    {u.archived_at && <Badge variant="neutral">Đã lưu trữ</Badge>}
                  </td>
                  <td style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    {u.role === 'kcs' && !u.archived_at && (
                      <button className="btn-outline btn-sm" onClick={() => openAreas(u)}>
                        Phân vùng
                      </button>
                    )}
                    <RowActionsMenu
                      user={u}
                      onEdit={() => openEdit(u)}
                      onStatus={(status) => updateStatus(u, status)}
                      onResetPassword={() => resetPassword(u)}
                      onArchive={() => archiveUser(u)}
                      onRestore={() => restoreUser(u)}
                      onHardDelete={() => openHardDelete(u)}
                    />
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={8} className="muted-note">
                    Không có dữ liệu.
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
        </>
      )}

      <Modal
        open={!!form}
        title={form?.id ? 'Sửa người dùng' : 'Thêm người dùng'}
        onClose={() => setForm(null)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setForm(null)}>
              Hủy
            </button>
            <button onClick={saveForm} disabled={saving}>
              Lưu
            </button>
          </>
        }
      >
        {form && (
          <div style={{ display: 'grid', gap: 10 }}>
            <label>
              Tài khoản
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </label>
            <label>
              Mật khẩu {form.id ? '(để trống nếu không đổi)' : '(để trống dùng mặc định)'}
              <input
                type="password"
                style={{ display: 'block', width: '100%' }}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </label>
            <label>
              Họ tên
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </label>
            <label>
              Vai trò
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Chức danh
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.job_title}
                onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              >
                {JOB_TITLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Nhà hàng
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.restaurant}
                onChange={(e) => setForm({ ...form, restaurant: e.target.value })}
              >
                <option value="">—</option>
                {restaurantOptions.results.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Trạng thái
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>

      <Modal
        open={!!areaUser}
        title={`Phân vùng — ${areaUser?.full_name || ''}`}
        onClose={() => setAreaUser(null)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setAreaUser(null)}>
              Hủy
            </button>
            <button onClick={saveAreas} disabled={areaSaving}>
              Lưu
            </button>
          </>
        }
      >
        <div style={{ display: 'grid', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {restaurantOptions.results.map((r) => (
            <label key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={areaSelected.includes(r.id)}
                onChange={() => toggleArea(r.id)}
              />
              {r.name}
            </label>
          ))}
        </div>
      </Modal>

      <Modal
        open={!!resetResult}
        title="Đã đặt lại mật khẩu"
        onClose={() => setResetResult(null)}
        footer={<button onClick={() => setResetResult(null)}>Đóng</button>}
      >
        {resetResult && (
          <div>
            <p>
              Tài khoản <b>{resetResult.username}</b> — mật khẩu tạm:{' '}
              <b style={{ fontSize: 18 }}>{resetResult.password}</b>
            </p>
            <p className="muted-note">
              Chỉ hiển thị 1 lần này — hãy copy đưa cho người dùng. Người dùng sẽ bị bắt buộc đổi
              mật khẩu ngay khi đăng nhập lần kế tiếp.
            </p>
          </div>
        )}
      </Modal>

      <Modal
        open={!!deleteTarget}
        title="Xóa cứng tài khoản"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setDeleteTarget(null)}>Hủy</button>
            <button
              className="btn-danger"
              onClick={confirmHardDelete}
              disabled={deleting || deleteConfirmText !== deleteTarget?.username}
            >
              Xóa vĩnh viễn
            </button>
          </>
        }
      >
        {deleteTarget && (
          <div>
            <p style={{ color: 'var(--danger)' }}>
              Hành động này KHÔNG THỂ hoàn tác. Chỉ xóa được khi tài khoản chưa phát sinh dữ liệu
              đào tạo/thi/hoa hồng/đánh giá — nếu không sẽ bị chặn, dùng "Lưu trữ" thay thế.
            </p>
            <label>
              Gõ lại tên tài khoản <b>{deleteTarget.username}</b> để xác nhận
              <input
                style={{ display: 'block', width: '100%' }}
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
              />
            </label>
            {deleteError && <p style={{ color: 'var(--danger)', marginTop: 8 }}>{deleteError}</p>}
          </div>
        )}
      </Modal>

      <Modal
        open={bulkDeleteOpen}
        title="Xóa cứng các tài khoản đã chọn"
        onClose={() => setBulkDeleteOpen(false)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setBulkDeleteOpen(false)}>Hủy</button>
            <button
              className="btn-danger"
              onClick={confirmBulkDelete}
              disabled={bulkBusy || bulkDeleteConfirmText.trim().toUpperCase() !== 'XÓA'}
            >
              Xóa vĩnh viễn {selectedUsers.length} tài khoản
            </button>
          </>
        }
      >
        <div>
          <p style={{ color: 'var(--danger)' }}>
            Hành động này KHÔNG THỂ hoàn tác. Chỉ những tài khoản chưa phát sinh dữ liệu đào tạo/
            thi/hoa hồng/đánh giá mới xóa được — các tài khoản còn vướng sẽ bị chặn (dùng "Lưu trữ"
            thay thế) và được báo rõ lý do sau khi thực hiện.
          </p>
          <ul style={{ maxHeight: 160, overflowY: 'auto', margin: '8px 0' }}>
            {selectedUsers.map((u) => (
              <li key={u.id}>{u.username} — {u.full_name}</li>
            ))}
          </ul>
          <label>
            Gõ <b>XÓA</b> để xác nhận
            <input
              style={{ display: 'block', width: '100%' }}
              value={bulkDeleteConfirmText}
              onChange={(e) => setBulkDeleteConfirmText(e.target.value)}
            />
          </label>
        </div>
      </Modal>
      </>
      )}
    </AppShell>
  )
}
