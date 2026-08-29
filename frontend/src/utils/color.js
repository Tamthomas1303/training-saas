// Tien ich mau thuan JS (khong them thu vien) - UI dot 1, Prompt_UI_Dot1_Theme.md muc 3c.

function hexToRgb(hex) {
  let h = (hex || '').replace('#', '').trim()
  if (h.length === 3) {
    h = h.split('').map((c) => c + c).join('')
  }
  const num = parseInt(h, 16) || 0
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 }
}

function clamp255(n) {
  return Math.max(0, Math.min(255, Math.round(n)))
}

function rgbToHex(r, g, b) {
  const toHex = (n) => clamp255(n).toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

// shade(hex, -0.14) -> toi di 14%. shade(hex, 0.14) -> sang len 14%.
export function shade(hex, amt) {
  const { r, g, b } = hexToRgb(hex)
  const target = amt < 0 ? 0 : 255
  const p = Math.abs(amt)
  return rgbToHex(
    (target - r) * p + r,
    (target - g) * p + g,
    (target - b) * p + b,
  )
}

// mix(hex1, hex2, ratio) -> pha hex1 voi hex2 theo ty le ratio la trong so cua hex2 (vd
// mix(brand, '#ffffff', 0.90) = 10% brand + 90% trang, dung cho nen rat nhat --brand-soft).
export function mix(hex1, hex2, ratio) {
  const a = hexToRgb(hex1)
  const b = hexToRgb(hex2)
  return rgbToHex(
    a.r * (1 - ratio) + b.r * ratio,
    a.g * (1 - ratio) + b.g * ratio,
    a.b * (1 - ratio) + b.b * ratio,
  )
}

// Dung cho fill trong suot tren bieu do (RadarChart) - hex khong ho tro alpha, can rgba().
export function hexToRgba(hex, alpha) {
  const { r, g, b } = hexToRgb(hex)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// Ghi 3 bien CSS --brand/--brand-dark/--brand-soft len :root - goi 1 LAN sau khi biet brand cua
// user dang nhap (xem AuthContext). Khong truyen brand_hex hop le -> khong lam gi (giu mac dinh
// CSS tinh trong theme.css).
export function applyBrand(brandHex) {
  if (!brandHex || !/^#[0-9a-fA-F]{6}$/.test(brandHex)) return
  const root = document.documentElement
  root.style.setProperty('--brand', brandHex)
  root.style.setProperty('--brand-dark', shade(brandHex, -0.14))
  root.style.setProperty('--brand-soft', mix(brandHex, '#ffffff', 0.90))
  // Prompt_Fix_DotA_29.08.md muc 4: mau dau gradient trang tri (thanh tien do/nut/the) - brand pha
  // trang ~35%, thay cho --green co dinh #68BA7F khong doi theo brand truoc day.
  root.style.setProperty('--brand-light', mix(brandHex, '#ffffff', 0.35))
}
