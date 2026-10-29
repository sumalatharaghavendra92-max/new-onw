// A primary panel: surface plus the tinted shadow from operations.css.
export default function Card({ children, className = '' }) {
  return <div className={`op-panel ${className}`}>{children}</div>;
}
