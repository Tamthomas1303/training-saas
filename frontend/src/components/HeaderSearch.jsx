import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

export default function HeaderSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const boxRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    const timeout = setTimeout(() => {
      api
        .get('/employees/', { params: { search: query, page_size: 8 } })
        .then(({ data }) => {
          setResults(data.results)
          setOpen(true)
        })
        .catch(() => setResults([]))
    }, 300)
    return () => clearTimeout(timeout)
  }, [query])

  function pick(emp) {
    setQuery('')
    setResults([])
    setOpen(false)
    navigate(`/employees/${emp.id}`)
  }

  return (
    <div ref={boxRef} className="header-search">
      <span className="header-search-icon">🔍</span>
      <input
        className="header-search-input"
        placeholder="Tìm nhân sự theo tên / mã..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="header-search-results">
          {results.map((emp) => (
            <div key={emp.id} className="header-search-result-item" onClick={() => pick(emp)}>
              <span>{emp.name}</span>
              <span className="muted-note" style={{ fontSize: 12 }}>
                {emp.code}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
