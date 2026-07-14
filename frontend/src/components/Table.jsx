export default function Table({ children, ...props }) {
  return (
    <table className="themed" {...props}>
      {children}
    </table>
  )
}
