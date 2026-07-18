export default function Table({ children, ...props }) {
  return (
    <div className="table-scroll">
      <table className="themed" {...props}>
        {children}
      </table>
    </div>
  )
}
