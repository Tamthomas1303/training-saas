import { useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import Table from '../components/Table'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 10

export default function RestaurantsPage() {
  const [search, setSearch] = useState('')
  const [brand, setBrand] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const params = { search, brand, status, page, page_size: PAGE_SIZE }
  const { data, loading, error } = usePaginatedList('/restaurants/', params)

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  return (
    <AppShell>
      <h2>Nhà hàng</h2>

      <FilterBar>
        <input
          style={s.input}
          placeholder="Tìm theo mã / tên / email..."
          value={search}
          onChange={onFilterChange(setSearch)}
        />
        <input
          style={s.input}
          placeholder="Lọc theo brand"
          value={brand}
          onChange={onFilterChange(setBrand)}
        />
        <select style={s.select} value={status} onChange={onFilterChange(setStatus)}>
          <option value="">Tất cả trạng thái</option>
          <option value="active">Đang hoạt động</option>
          <option value="inactive">Ngừng hoạt động</option>
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>Mã</th>
                <th>Tên nhà hàng</th>
                <th>Brand</th>
                <th>Khu vực</th>
                <th>Email</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td>
                  <td>{r.name}</td>
                  <td>{r.brand}</td>
                  <td>{[r.city, r.district, r.region].filter(Boolean).join(' · ')}</td>
                  <td>{r.email}</td>
                  <td>
                    <Badge variant={r.status === 'active' ? 'success' : 'neutral'}>
                      {r.status === 'active' ? 'Đang hoạt động' : 'Ngừng hoạt động'}
                    </Badge>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted-note">
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
