// Thin wrapper over the shared .op-button styles in operations.css.
const VARIANTS = {
  primary: 'op-button',
  secondary: 'op-button secondary',
  outline: 'op-button secondary',
  ghost: 'op-button secondary',
  danger: 'op-button danger',
};

export default function Button({ children, variant = 'primary', className = '', ...props }) {
  return (
    <button className={`${VARIANTS[variant] || VARIANTS.primary} ${className}`} {...props}>
      {children}
    </button>
  );
}
