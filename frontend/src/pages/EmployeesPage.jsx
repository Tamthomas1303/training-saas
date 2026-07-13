import { useState } from 'react'
import NavBar from '../components/NavBar'
import Pager from '../components/Pager'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_LABELS = {
  probation: 'Thử việc',
  active: 'Chính thức',
  resigned: 'Nghỉ việc',
}

export default function EmployeesPage() {
  const [search, setSearch] = useState('')
  const [restaurant, setRestaurant] = useState('')
  const [employeeStatus, setEmployeeStatus] = useState('')
  const [page, setPage] = useState(1)

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })

  const params = {
    search,
    restaurant: restaurant || undefined,
    employee_status: employeeStatus || undefined,
    page,
    page_size: PAGE_SIZE,
  }
  const { data, loading, error } = usePaginatedList('/employees/', params)

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  return (
    <div style={s.page}>
      <NavBar />
      <h2>Nhân sự</h2>

      <div style={s.toolbar}>
        <input
          style={s.input}
          placeholder="Tìm theo mã / tên nhân viên..."
          value={search}
          onChange={onFilterChange(setSearch)}
        />
        <select style={s.select} value={restaurant} onChange={onFilterChange(setRestaurant)}>
          <option value="">Tất cả nhà hàng</option>
          {restaurantOptions.results.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        <select style={s.select} value={employeeStatus} onChange={onFilterChange(setEmployeeStatus)}>
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {loading && <p>Đang tải...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && !error && (
        <>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Mã NV</th>
                <th style={s.th}>Họ tên</th>
                <th style={s.th}>Nhà hàng</th>
                <th style={s.th}>Vị trí</th>
                <th style={s.th}>Ngày vào</th>
                <th style={s.th}>Trạng thái</th>
                <th style={s.th}>Kết quả TV</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e) => (
                <tr key={e.id}>
                  <td style={s.td}>{e.code}</td>
                  <td style={s.td}>{e.name}</td>
                  <td style={s.td}>{e.restaurant_name}</td>
                  <td style={s.td}>{e.position}</td>
                  <td style={s.td}>{e.start_date}</td>
                  <td style={s.td}>{STATUS_LABELS[e.employee_status] || e.employee_status}</td>
                  <td style={s.td}>{e.final_result}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td style={s.td} colSpan={7}>
                    Không có dữ liệu.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
        </>
      )}
    </div>
  )
}
