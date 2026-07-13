import { useState } from 'react'
import NavBar from '../components/NavBar'
import Pager from '../components/Pager'
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
    <div style={s.page}>
      <NavBar />
      <h2>Nhà hàng</h2>

      <div style={s.toolbar}>
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
      </div>

      {loading && <p>Đang tải...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && !error && (
        <>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Mã</th>
                <th style={s.th}>Tên nhà hàng</th>
                <th style={s.th}>Brand</th>
                <th style={s.th}>Khu vực</th>
                <th style={s.th}>Email</th>
                <th style={s.th}>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.id}>
                  <td style={s.td}>{r.code}</td>
                  <td style={s.td}>{r.name}</td>
                  <td style={s.td}>{r.brand}</td>
                  <td style={s.td}>{[r.city, r.district, r.region].filter(Boolean).join(' · ')}</td>
                  <td style={s.td}>{r.email}</td>
                  <td style={s.td}>{r.status === 'active' ? 'Đang hoạt động' : 'Ngừng hoạt động'}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td style={s.td} colSpan={6}>
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
