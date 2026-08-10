// Port EmployeeService.gs::canTrainPosition (client-side mirror cua backend
// employees/permissions.py::can_train_position) - dung de an/hien nut "Đào tạo".
function normalizeKey(value) {
  // Bỏ DẤU tiếng Việt để khớp giống hệt backend permissions.py::_normalize_key.
  return (value || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'd')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
}

export function canTrainPosition(role, jobPosition) {
  const r = (role || '').toLowerCase()
  const p = normalizeKey(jobPosition)
  const isQl = p.includes('quan ly') || p.includes('quan li') || p.includes('qlnh')
  const isBt = p.includes('bep truong')
  const isGs = p.includes('giam sat')
  const isBp = p.includes('bep pho')

  if (r === 'admin') return true
  if (r === 'am') return isQl
  if (r === 'kcs') return isBt
  if (r === 'bql') return !(isQl || isBt)
  if (r === 'trainer') return !(isQl || isBt || isGs || isBp)
  return false
}
