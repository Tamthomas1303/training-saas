import { useState } from 'react'
import NavBar from '../components/NavBar'
import Pager from '../components/Pager'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

export default function ChecklistPage() {
  const [search, setSearch] = useState('')
  const [brand, setBrand] = useState('')
  const [position, setPosition] = useState('')
  const [page, setPage] = useState(1)

  const params = { search, brand: brand || undefined, position: position || undefined, page, page_size: PAGE_SIZE }
  const { data, loading, error } = usePaginatedList('/checklist/', params)

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  return (
    <div style={s.page}>
      <NavBar />
      <h2>Checklist đào tạo</h2>

      <div style={s.toolbar}>
        <input
          style={s.input}
          placeholder="Tìm theo tên đầu việc..."
          value={search}
          onChange={onFilterChange(setSearch)}
        />
        <input style={s.input} placeholder="Lọc theo brand" value={brand} onChange={onFilterChange(setBrand)} />
        <input
          style={s.input}
          placeholder="Lọc theo vị trí"
          value={position}
          onChange={onFilterChange(setPosition)}
        />
      </div>

      {loading && <p>Đang tải...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && !error && (
        <>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>#</th>
                <th style={s.th}>Brand</th>
                <th style={s.th}>Vị trí</th>
                <th style={s.th}>Ngày</th>
                <th style={s.th}>Danh mục</th>
                <th style={s.th}>Đầu việc</th>
                <th style={s.th}>Cấp</th>
                <th style={s.th}>Tài liệu</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((c) => (
                <tr key={c.id}>
                  <td style={s.td}>{c.order}</td>
                  <td style={s.td}>{c.brand}</td>
                  <td style={s.td}>{c.position}</td>
                  <td style={s.td}>{c.day}</td>
                  <td style={s.td}>{c.category}</td>
                  <td style={s.td}>{c.task_name}</td>
                  <td style={s.td}>{c.level_group}</td>
                  <td style={s.td}>
                    {c.doc_url ? (
                      <a href={c.doc_url} target="_blank" rel="noreferrer">
                        Xem
                      </a>
                    ) : (
                      ''
                    )}
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td style={s.td} colSpan={8}>
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
