import { useEffect, useState } from 'react'
import api from '../api/client'

// Danh sach nang luc (dashboard.Competency) dung cho dropdown gan nhan o nhieu man (Course/
// Exam/Tieu chi danh gia/Checklist) - nap 1 lan, sap theo nhom.
export function useCompetencyOptions() {
  const [options, setOptions] = useState([])

  useEffect(() => {
    api.get('/dashboard/competencies/', { params: { page_size: 200 } })
      .then(({ data }) => {
        const sorted = [...data.results].sort(
          (a, b) => (a.group_code || '').localeCompare(b.group_code || '') || (a.order || 0) - (b.order || 0),
        )
        setOptions(sorted)
      })
      .catch(() => setOptions([]))
  }, [])

  return options
}
