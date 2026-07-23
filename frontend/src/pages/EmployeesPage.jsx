import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Pager from '../components/Pager'
import ProgressBar from '../components/ProgressBar'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_LABELS = { probation: 'Thử việc', active: 'Chính thức', resigned: 'Nghỉ việc' }
const STATUS_VARIANTS = { probation: 'warning', active: 'success', resigned: 'neutral' }
const OPERATION_UNITS = [
  { value: 'restaurant', label: 'Nhà hàng' },
  { value: 'office', label: 'Văn phòng' },
  { value: 'production', label: 'Sản xuất' },
]

const TRAINING_STATUS_OPTIONS = [
  { value: '', label: 'Tất cả tiến độ' },
  { value: 'in_progress', label: 'Đang đào tạo' },
  { value: 'not_started', label: 'Chưa đào tạo' },
  { value: 'done', label: 'Hoàn thành' },
]

const EMPTY_EMP = {
  code: '', name: '', position: '', restaurant: '', operation_unit: 'restaurant',
  start_date: '', employee_status: 'probation',
}

function LmsMark({ ok }) {
  return (
    <span style={{ color: ok ? 'var(--forest-dark)' : 'var(--danger)', fontSize: 15 }} title={ok ? 'Đã hoàn thành' : 'Chưa hoàn thành'}>
      {ok ? '✅' : '☒'}
    </span>
  )
}

export default function EmployeesPage() {
  const { user } = useAuth()
  const isAdmin = ['admin', 'om'].includes((user?.role || '').toLowerCase())

  const [search, setSearch] = useState('')
  const [restaurant, setRestaurant] = useState('')
  const [employeeStatus, setEmployeeStatus] = useState('')
  const [trainingStatus, setTrainingStatus] = useState('')
  const [staffKind, setStaffKind] = useState('new') // 'new' | 'legacy' | '' (tất cả)
  const [order, setOrder] = useState('oldest')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [positions, setPositions] = useState([])
  const [showImport, setShowImport] = useState(false)
  const [sourceUrl, setSourceUrl] = useState('')
  const [importMsg, setImportMsg] = useState('')
  const [importBusy, setImportBusy] = useState(false)
  const fileRef = useRef(null)
  const examRef = useRef(null)
  const evalRef = useRef(null)
  const [hrSources, setHrSources] = useState([])
  const [hrMsg, setHrMsg] = useState('')

  useEffect(() => {
    api.get('/employees/positions/').then(({ data }) => setPositions(data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (isAdmin) {
      api.get('/employees/recruitment-source/').then(({ data }) => setSourceUrl(data.csv_url || '')).catch(() => {})
      api.get('/employees/hr-sync-sources/').then(({ data }) => setHrSources(data)).catch(() => {})
    }
  }, [isAdmin])

  async function saveHrSource(kind, csv_url) {
    try {
      await api.put('/employees/hr-sync-sources/', { kind, csv_url })
    } catch { /* im lặng */ }
  }
  async function runHrSync(url, label) {
    setImportBusy(true)
    setHrMsg(`Đang ${label}...`)
    try {
      const { data } = await api.post(url)
      setHrMsg(`${label}: ${JSON.stringify(data)}`)
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setHrMsg(e.response?.data?.detail || `${label} thất bại.`)
    } finally {
      setImportBusy(false)
    }
  }

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })

  const params = {
    search,
    restaurant: restaurant || undefined,
    employee_status: employeeStatus || undefined,
    training_status: trainingStatus || undefined,
    is_legacy: staffKind === 'new' ? false : staffKind === 'legacy' ? true : undefined,
    ordering: order === 'newest' ? '-start_date' : 'start_date',
    page,
    page_size: PAGE_SIZE,
    refreshKey,
  }
  const { data, loading, error } = usePaginatedList('/employees/', params)

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  async function saveEmployee() {
    setSaving(true)
    setFormError('')
    try {
      await api.post('/employees/', { ...form, restaurant: form.restaurant || null })
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được nhân sự.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function deleteEmployee(id, name) {
    if (!window.confirm(`Xóa nhân sự "${name}"? Hành động này không hoàn tác.`)) return
    try {
      await api.delete(`/employees/${id}/`)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      alert(err.response?.data?.detail || 'Không xóa được nhân sự.')
    }
  }

  function statLine(st) {
    return (
      `Xong: ${st.created} tạo mới, ${st.updated} cập nhật, ${st.skipped} bỏ qua` +
      (st.unmatched_restaurant ? `, ${st.unmatched_restaurant} không khớp nhà hàng` : '') + '.'
    )
  }
  async function uploadFile(file) {
    if (!file) return
    setImportBusy(true)
    setImportMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const { data } = await api.post('/employees/import-file/', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setImportMsg(statLine(data))
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setImportMsg(e.response?.data?.detail || 'Nhập file thất bại.')
    } finally {
      setImportBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }
  async function uploadHistory(file, url, ref, label) {
    if (!file) return
    setImportBusy(true)
    setImportMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const { data } = await api.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setImportMsg(`${label}: ${data.created} tạo mới, ${data.updated ?? 0} cập nhật, ${data.skipped} bỏ qua / ${data.total} dòng.`)
    } catch (e) {
      setImportMsg(e.response?.data?.detail || `Nhập ${label} thất bại.`)
    } finally {
      setImportBusy(false)
      if (ref.current) ref.current.value = ''
    }
  }
  async function saveSource() {
    setImportBusy(true)
    setImportMsg('')
    try {
      await api.put('/employees/recruitment-source/', { csv_url: sourceUrl })
      setImportMsg('Đã lưu link nguồn.')
    } catch (e) {
      setImportMsg(e.response?.data?.detail || 'Lưu link thất bại.')
    } finally {
      setImportBusy(false)
    }
  }
  async function syncNow() {
    setImportBusy(true)
    setImportMsg('')
    try {
      const { data } = await api.post('/employees/sync-now/')
      setImportMsg(statLine(data))
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setImportMsg(e.response?.data?.detail || 'Đồng bộ thất bại.')
    } finally {
      setImportBusy(false)
    }
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Nhân sự</h2>
        {isAdmin && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn-outline" onClick={() => setShowImport((v) => !v)}>Nhập dữ liệu ▾</button>
            <button onClick={() => { setForm({ ...EMPTY_EMP }); setFormError('') }}>+ Thêm nhân sự</button>
          </div>
        )}
      </div>

      {isAdmin && showImport && (
        <div className="card" style={{ margin: '12px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Cách 2 — Nhập từ file (Excel .xlsx hoặc CSV)</div>
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xlsm,.csv"
              disabled={importBusy}
              onChange={(e) => uploadFile(e.target.files[0])}
            />
            <div className="muted-note" style={{ fontSize: 12 }}>
              Cột cần có: Employee_ID, Employee_Name, Restaurant_Name, Job_Position, Operation_Unit, Job_Level, Start_Date, Employee_Status.
              <br />Dữ liệu cũ (tuỳ chọn): Current_Level, Join_Date, Positions_Achieved (các vị trí đã đạt, phân tách bằng dấu “;”).
            </div>
          </div>

          <div style={{ borderTop: '1px solid var(--card-border)', paddingTop: 12, marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Dữ liệu cũ — Kết quả thi lịch sử (BQL/CLS)</div>
            <input ref={examRef} type="file" accept=".xlsx,.xlsm,.csv" disabled={importBusy}
              onChange={(e) => uploadHistory(e.target.files[0], '/employees/import-exam-history/', examRef, 'Kết quả thi')} />
            <div className="muted-note" style={{ fontSize: 12 }}>Cột: Employee_ID, Exam_Name, Exam_Date, Score, Result, Position.</div>
          </div>

          <div style={{ borderTop: '1px solid var(--card-border)', paddingTop: 12, marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Dữ liệu cũ — Đánh giá lịch sử</div>
            <input ref={evalRef} type="file" accept=".xlsx,.xlsm,.csv" disabled={importBusy}
              onChange={(e) => uploadHistory(e.target.files[0], '/employees/import-eval-history/', evalRef, 'Đánh giá')} />
            <div className="muted-note" style={{ fontSize: 12 }}>Cột: Employee_ID, Eval_Type, Position, Percent, Result, Date.</div>
          </div>
          <div style={{ borderTop: '1px solid var(--card-border)', paddingTop: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Cách 3 — Tự đồng bộ từ Google Sheet</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                style={{ flex: 1, minWidth: 240 }}
                placeholder="Dán link CSV (Google Sheet: File > Share > Publish to web > CSV)..."
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
              <button className="btn-outline" onClick={saveSource} disabled={importBusy}>Lưu link</button>
              <button onClick={syncNow} disabled={importBusy}>Đồng bộ ngay</button>
            </div>
            <div className="muted-note" style={{ fontSize: 12 }}>
              Tự động đồng bộ mỗi 2 giờ trong khung 8h–19h. Chỉ cần dán link ở đây một lần, không cần vào GitHub.
            </div>
          </div>
          {importBusy && <p className="muted-note">Đang xử lý...</p>}
          {importMsg && <p style={{ color: 'var(--forest-dark)' }}>{importMsg}</p>}

          <div style={{ borderTop: '2px solid var(--forest)', paddingTop: 12, marginTop: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Auto Syncing - HR Data (v2.1) — dán link CSV từng tab</div>
            <div className="muted-note" style={{ fontSize: 12, marginBottom: 8 }}>
              Mỗi tab của Google Sheet: File → Chia sẻ → Xuất bản lên web → CSV. Dán link tương ứng rồi bấm đồng bộ.
              Roster hợp nhất các tab nhân sự (ưu tiên nhân sự mới sau 1/7). Nạp lịch sử cần đồng bộ roster trước.
            </div>
            {hrSources.map((s, i) => (
              <div key={s.kind} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                <span style={{ minWidth: 190, fontSize: 12 }}>{s.label}</span>
                <input
                  style={{ flex: 1, minWidth: 200 }}
                  placeholder="Dán link CSV..."
                  defaultValue={s.csv_url}
                  onChange={(e) => { const next = [...hrSources]; next[i] = { ...s, csv_url: e.target.value }; setHrSources(next) }}
                  onBlur={(e) => saveHrSource(s.kind, e.target.value)}
                />
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <button onClick={() => runHrSync('/employees/hr-sync-roster/', 'Đồng bộ roster')} disabled={importBusy}>Đồng bộ roster</button>
              <button className="btn-outline" onClick={() => runHrSync('/employees/hr-sync-history/', 'Nạp lịch sử')} disabled={importBusy}>Nạp lịch sử (Pass/khóa/cấp O)</button>
            </div>
            {hrMsg && <p style={{ color: 'var(--forest-dark)', fontSize: 12, wordBreak: 'break-all' }}>{hrMsg}</p>}
          </div>
        </div>
      )}

      <FilterBar>
        <input style={s.input} placeholder="Tìm theo mã / tên nhân viên..." value={search} onChange={onFilterChange(setSearch)} />
        <select style={s.select} value={staffKind} onChange={onFilterChange(setStaffKind)}>
          <option value="new">Nhân sự mới</option>
          <option value="legacy">Nhân sự cũ</option>
          <option value="">Tất cả</option>
        </select>
        <select style={s.select} value={restaurant} onChange={onFilterChange(setRestaurant)}>
          <option value="">Tất cả nhà hàng</option>
          {restaurantOptions.results.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
        <select style={s.select} value={employeeStatus} onChange={onFilterChange(setEmployeeStatus)}>
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select style={s.select} value={trainingStatus} onChange={onFilterChange(setTrainingStatus)}>
          {TRAINING_STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <button className={`btn-sm ${order === 'oldest' ? '' : 'btn-outline'}`} onClick={() => { setOrder('oldest'); setPage(1) }}>Cũ nhất</button>
        <button className={`btn-sm ${order === 'newest' ? '' : 'btn-outline'}`} onClick={() => { setOrder('newest'); setPage(1) }}>Mới nhất</button>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>Họ tên</th>
                <th>Nhà hàng</th>
                <th>Vị trí</th>
                <th>Ngày vào</th>
                <th>Trạng thái</th>
                <th>Tiến độ</th>
                <th>LMS/Đánh giá</th>
                <th>Kết quả TV</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e) => (
                <tr key={e.id}>
                  <td>{e.name} - {e.code}</td>
                  <td>{e.restaurant_name}</td>
                  <td>{e.position}</td>
                  <td>{e.start_date}</td>
                  <td>
                    <Badge variant={STATUS_VARIANTS[e.employee_status] || 'neutral'}>
                      {STATUS_LABELS[e.employee_status] || e.employee_status}
                    </Badge>
                  </td>
                  <td style={{ minWidth: 100 }}>
                    <ProgressBar percent={e.progress_percent} />
                    <div className="muted-note" style={{ fontSize: 12 }}>{e.progress_percent}%</div>
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <LmsMark ok={e.lms_marks?.course} /> <LmsMark ok={e.lms_marks?.exam} /> <LmsMark ok={e.lms_marks?.skill} />
                  </td>
                  <td>{e.final_result}</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <Link to={`/employees/${e.id}`}>
                      <button className="btn-outline btn-sm">Chi tiết</button>
                    </Link>
                    {isAdmin && (
                      <button
                        className="btn-outline btn-sm"
                        style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
                        onClick={() => deleteEmployee(e.id, e.name)}
                      >
                        Xóa
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={9} className="muted-note">Không có dữ liệu.</td>
                </tr>
              )}
            </tbody>
          </Table>
          <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
        </>
      )}

      <Modal
        open={!!form}
        title="Thêm nhân sự"
        onClose={() => setForm(null)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setForm(null)}>Hủy</button>
            <button onClick={saveEmployee} disabled={saving}>Lưu</button>
          </>
        }
      >
        {form && (
          <div style={{ display: 'grid', gap: 10 }}>
            <label>
              Mã nhân viên
              <input style={{ display: 'block', width: '100%' }} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </label>
            <label>
              Họ tên
              <input style={{ display: 'block', width: '100%' }} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label>
              Vị trí
              <input
                list="emp-position-list"
                style={{ display: 'block', width: '100%' }}
                value={form.position}
                onChange={(e) => setForm({ ...form, position: e.target.value })}
                placeholder="Chọn hoặc gõ để lọc vị trí..."
              />
              <datalist id="emp-position-list">
                {positions.map((p) => (
                  <option key={p} value={p} />
                ))}
              </datalist>
            </label>
            <label>
              Nhà hàng
              <select style={{ display: 'block', width: '100%' }} value={form.restaurant} onChange={(e) => setForm({ ...form, restaurant: e.target.value })}>
                <option value="">—</option>
                {restaurantOptions.results.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </label>
            <label>
              Khối
              <select style={{ display: 'block', width: '100%' }} value={form.operation_unit} onChange={(e) => setForm({ ...form, operation_unit: e.target.value })}>
                {OPERATION_UNITS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
            <label>
              Ngày vào
              <input type="date" style={{ display: 'block', width: '100%' }} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </label>
            <label>
              Trạng thái
              <select style={{ display: 'block', width: '100%' }} value={form.employee_status} onChange={(e) => setForm({ ...form, employee_status: e.target.value })}>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>
    </AppShell>
  )
}
