import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './theme.css'
import App from './App.jsx'

// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 2) - dang ky service worker (chi lo web push + click,
// khong cache app). Bo qua im lang neu trinh duyet khong ho tro.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
