import { useEffect, useState } from 'react'
import api from '../api/client'

// Prompt_Fix_TrangTrang_MapUndefined.md (Phan 2) - chuan hoa response VE DUNG {count, results}
// bat ke backend that su tra ve gi (mang thuan, {results: null}, endpoint sai duong dan tra ve
// object khac hoan toan do loi routing...). Day la NGUON GOC that su cua man /employees bi trang
// (1 router phu ben backend vo tinh nuot mat list-view, tra ve object khac shape hoan toan) - da
// sua tan goc o backend, nhung van giu lop phong thu nay o day vi MOI trang dung usePaginatedList
// deu goi data.results.map(...) truc tiep (xem EmployeesPage/StudentDetailPage/...).
function normalizeListResponse(raw) {
  if (Array.isArray(raw)) return { count: raw.length, results: raw }
  if (raw && Array.isArray(raw.results)) return raw
  return { count: 0, results: [] }
}

export function usePaginatedList(endpoint, params) {
  const [data, setData] = useState({ count: 0, results: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const paramsKey = JSON.stringify(params)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api
      .get(endpoint, { params })
      .then(({ data }) => {
        if (active) setData(normalizeListResponse(data))
      })
      .catch(() => {
        if (active) setError('Không tải được dữ liệu.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, paramsKey])

  return { data, loading, error }
}
