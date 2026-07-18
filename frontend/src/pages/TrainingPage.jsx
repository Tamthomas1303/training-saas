import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import Table from '../components/Table'
import TrainingItemEditor from '../components/TrainingItemEditor'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import { canTrainPosition } from '../utils/canTrainPosition'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_LABELS = {
  pending: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Hoàn thành',
}

const STATUS_VARIANTS = {
  pending: 'neutral',
  in_progress: 'mint',
  done: 'success',
}

function groupByDayAndCategory(items) {
  const byDay = {}
  for (const item of items) {
    const day = item.checklist.day ?? 'Khác'
    const category = item.checklist.category || 'Khác'
    if (!byDay[day]) byDay[day] = {}
    if (!byDay[day][category]) byDay[day][category] = []
    byDay[day][category].push(item)
  }
  return byDay
}

export default function TrainingPage() {
  const { user } = useAuth()
  const location = useLocation()
  const [employeeSearch, setEmployeeSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [checklistData, setChecklistData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [openItemId, setOpenItemId] = useState(null)

  const { data: employeeOptions } = usePaginatedList('/employees/', {
    search: employeeSearch,
    page,
    page_size: PAGE_SIZE,
  })

  async function selectEmployee(emp) {
    setSelectedEmployee(emp)
    setOpenItemId(null)
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get('/checklist/training/', { params: { employee: emp.id } })
      setChecklistData(data)
    } catch {
      setError('Không tải được checklist.')
    } finally {
      setLoading(false)
    }
  }

  function backToPicker() {
    setSelectedEmployee(null)
    setChecklistData(null)
    setOpenItemId(null)
  }

  // Vào từ nút "Bắt đầu đào tạo" ở Trang chủ → tự chọn nhân sự luôn
  useEffect(() => {
    if (location.state?.employee) selectEmployee(location.state.employee)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleSaved(checklistId, progress) {
    setChecklistData((prev) => ({
      ...prev,
      items: prev.items.map((it) => (it.checklist.id === checklistId ? { ...it, progress } : it)),
    }))
  }

  const grouped = checklistData ? groupByDayAndCategory(checklistData.items) : {}
  const days = Object.keys(grouped).sort((a, b) => Number(a) - Number(b))

  return (
    <AppShell>
      <h2>Đào tạo</h2>

      {!selectedEmployee && (
        <>
          <FilterBar>
            <input
              style={s.input}
              placeholder="Tìm nhân sự theo mã / tên để bắt đầu đào tạo..."
              value={employeeSearch}
              onChange={(e) => {
                setEmployeeSearch(e.target.value)
                setPage(1)
              }}
            />
            {employeeSearch && (
              <button
                className="btn-outline btn-sm"
                onClick={() => {
                  setEmployeeSearch('')
                  setPage(1)
                }}
              >
                Bỏ chọn
              </button>
            )}
          </FilterBar>
          <Table>
            <thead>
              <tr>
                <th>Mã NV</th>
                <th>Họ tên</th>
                <th>Nhà hàng</th>
                <th>Vị trí</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {employeeOptions.results.map((emp) => (
                <tr key={emp.id}>
                  <td>{emp.code}</td>
                  <td>{emp.name}</td>
                  <td>{emp.restaurant_name}</td>
                  <td>{emp.position}</td>
                  <td>
                    <button className="btn-outline btn-sm" onClick={() => selectEmployee(emp)}>
                      Chọn
                    </button>
                  </td>
                </tr>
              ))}
              {employeeOptions.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted-note">
                    Không có dữ liệu.
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
          <Pager page={page} pageSize={PAGE_SIZE} count={employeeOptions.count} onChange={setPage} />
        </>
      )}

      {selectedEmployee && (
        <>
          <p>
            <button className="btn-outline btn-sm" onClick={backToPicker}>
              « Chọn nhân sự khác
            </button>
          </p>
          <h3>
            {selectedEmployee.name} — {selectedEmployee.position} — {selectedEmployee.restaurant_name}
          </h3>

          {loading && <p className="muted-note">Đang tải...</p>}
          {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

          {checklistData && checklistData.items.length === 0 && (
            <p className="muted-note">Không tìm thấy checklist phù hợp (theo brand + vị trí) cho nhân sự này.</p>
          )}

          {days.map((day) => (
            <div key={day} style={{ marginBottom: 24 }}>
              <h4>Ngày {day}</h4>
              {Object.entries(grouped[day]).map(([category, items]) => (
                <div key={category} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 'bold', color: 'var(--muted)', margin: '8px 0 4px' }}>{category}</div>
                  {items.map((item) => {
                    const status = item.progress?.status || 'pending'
                    const allowed = canTrainPosition(user?.role, selectedEmployee.position)
                    return (
                      <div
                        key={item.checklist.id}
                        className="card"
                        style={{ marginBottom: 8, padding: 12 }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <strong>{item.checklist.task_name}</strong>
                            <div style={{ marginTop: 4 }}>
                              <Badge variant={STATUS_VARIANTS[status]}>{STATUS_LABELS[status]}</Badge>
                            </div>
                          </div>
                          <div>
                            {item.progress?.pdf_url && (
                              <a
                                href={item.progress.pdf_url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ marginRight: 8 }}
                              >
                                Xem biên bản
                              </a>
                            )}
                            {allowed ? (
                              <button
                                className="btn-sm"
                                onClick={() =>
                                  setOpenItemId(openItemId === item.checklist.id ? null : item.checklist.id)
                                }
                              >
                                {status === 'done' ? 'Sửa' : 'Đào tạo'}
                              </button>
                            ) : (
                              <span className="muted-note" style={{ fontSize: 12 }}>
                                Không có quyền đào tạo vị trí này
                              </span>
                            )}
                          </div>
                        </div>
                        {allowed && openItemId === item.checklist.id && (
                          <TrainingItemEditor
                            employeeId={selectedEmployee.id}
                            checklist={item.checklist}
                            progress={item.progress}
                            onSaved={(data) => handleSaved(item.checklist.id, data)}
                            onClose={() => setOpenItemId(null)}
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          ))}
        </>
      )}
    </AppShell>
  )
}
