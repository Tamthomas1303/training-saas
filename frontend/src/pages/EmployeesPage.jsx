import { useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import Table from '../components/Table'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_LABELS = {
  probation: 'Thử việc',
  active: 'Chính thức',
  resigned: 'Nghỉ việc',
}

const STATUS_VARIANTS = {
  probation: 'warning',
  active: 'success',
  resigned: 'neutral',
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
    <AppShell>
      <h2>Nhân sự</h2>

      <FilterBar>
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
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>Mã NV</th>
                <th>Họ tên</th>
                <th>Nhà hàng</th>
                <th>Vị trí</th>
                <th>Ngày vào</th>
                <th>Trạng thái</th>
                <th>Kết quả TV</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e) => (
                <tr key={e.id}>
                  <td>{e.code}</td>
                  <td>{e.name}</td>
                  <td>{e.restaurant_name}</td>
                  <td>{e.position}</td>
                  <td>{e.start_date}</td>
                  <td>
                    <Badge variant={STATUS_VARIANTS[e.employee_status] || 'neutral'}>
                      {STATUS_LABELS[e.employee_status] || e.employee_status}
                    </Badge>
                  </td>
                  <td>{e.final_result}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted-note">
                    Không có dữ liệu.
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
          <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
        </>
      )}
    </AppShell>
  )
}
