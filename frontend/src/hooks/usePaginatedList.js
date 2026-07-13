import { useEffect, useState } from 'react'
import api from '../api/client'

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
        if (active) setData(data)
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
