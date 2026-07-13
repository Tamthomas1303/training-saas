import { useState } from 'react'
import NavBar from '../components/NavBar'
import Pager from '../components/Pager'
import TrainingItemEditor from '../components/TrainingItemEditor'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_LABELS = {
  pending: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Hoàn thành',
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

  function handleSaved(checklistId, progress) {
    setChecklistData((prev) => ({
      ...prev,
      items: prev.items.map((it) => (it.checklist.id === checklistId ? { ...it, progress } : it)),
    }))
  }

  const grouped = checklistData ? groupByDayAndCategory(checklistData.items) : {}
  const days = Object.keys(grouped).sort((a, b) => Number(a) - Number(b))

  return (
    <div style={s.page}>
      <NavBar />
      <h2>Đào tạo</h2>

      {!selectedEmployee && (
        <>
          <div style={s.toolbar}>
            <input
              style={s.input}
              placeholder="Tìm nhân sự theo mã / tên để bắt đầu đào tạo..."
              value={employeeSearch}
              onChange={(e) => {
                setEmployeeSearch(e.target.value)
                setPage(1)
              }}
            />
          </div>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Mã NV</th>
                <th style={s.th}>Họ tên</th>
                <th style={s.th}>Nhà hàng</th>
                <th style={s.th}>Vị trí</th>
                <th style={s.th}></th>
              </tr>
            </thead>
            <tbody>
              {employeeOptions.results.map((emp) => (
                <tr key={emp.id}>
                  <td style={s.td}>{emp.code}</td>
                  <td style={s.td}>{emp.name}</td>
                  <td style={s.td}>{emp.restaurant_name}</td>
                  <td style={s.td}>{emp.position}</td>
                  <td style={s.td}>
                    <button onClick={() => selectEmployee(emp)}>Chọn</button>
                  </td>
                </tr>
              ))}
              {employeeOptions.results.length === 0 && (
                <tr>
                  <td style={s.td} colSpan={5}>
                    Không có dữ liệu.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <Pager page={page} pageSize={PAGE_SIZE} count={employeeOptions.count} onChange={setPage} />
        </>
      )}

      {selectedEmployee && (
        <>
          <p>
            <button onClick={backToPicker}>« Chọn nhân sự khác</button>
          </p>
          <h3>
            {selectedEmployee.name} — {selectedEmployee.position} — {selectedEmployee.restaurant_name}
          </h3>

          {loading && <p>Đang tải...</p>}
          {error && <p style={{ color: 'red' }}>{error}</p>}

          {checklistData && checklistData.items.length === 0 && (
            <p>Không tìm thấy checklist phù hợp (theo brand + vị trí) cho nhân sự này.</p>
          )}

          {days.map((day) => (
            <div key={day} style={{ marginBottom: 24 }}>
              <h4>Ngày {day}</h4>
              {Object.entries(grouped[day]).map(([category, items]) => (
                <div key={category} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 'bold', color: '#555', margin: '8px 0 4px' }}>{category}</div>
                  {items.map((item) => {
                    const status = item.progress?.status || 'pending'
                    return (
                      <div key={item.checklist.id} style={{ borderBottom: '1px solid #eee', padding: '8px 0' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <strong>{item.checklist.task_name}</strong>
                            <div style={{ fontSize: 13, color: '#666' }}>{STATUS_LABELS[status]}</div>
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
                            <button
                              onClick={() =>
                                setOpenItemId(openItemId === item.checklist.id ? null : item.checklist.id)
                              }
                            >
                              {status === 'done' ? 'Sửa' : 'Đào tạo'}
                            </button>
                          </div>
                        </div>
                        {openItemId === item.checklist.id && (
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
    </div>
  )
}
