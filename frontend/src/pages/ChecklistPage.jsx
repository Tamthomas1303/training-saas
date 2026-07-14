import { useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import Table from '../components/Table'
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
    <AppShell>
      <h2>Checklist đào tạo</h2>

      <FilterBar>
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
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>#</th>
                <th>Brand</th>
                <th>Vị trí</th>
                <th>Ngày</th>
                <th>Danh mục</th>
                <th>Đầu việc</th>
                <th>Cấp</th>
                <th>Tài liệu</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((c) => (
                <tr key={c.id}>
                  <td>{c.order}</td>
                  <td>{c.brand}</td>
                  <td>{c.position}</td>
                  <td>{c.day}</td>
                  <td>{c.category}</td>
                  <td>{c.task_name}</td>
                  <td>{c.level_group}</td>
                  <td>
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
                  <td colSpan={8} className="muted-note">
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
