export default function Modal({ open, title, onClose, children, footer }) {
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        {title && <h3 className="modal-title">{title}</h3>}
        {children}
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
