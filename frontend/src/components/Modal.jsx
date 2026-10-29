import { X } from 'lucide-react';

export default function Modal({ isOpen, onClose, title, children }) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgb(15 53 39 / 0.45)' }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="op-panel flush w-full max-w-lg flex flex-col overflow-hidden">
        <div className="flex justify-between items-center px-6 py-4 border-b border-neutral-border">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} className="op-icon-button" aria-label="Close">
            <X size={20} />
          </button>
        </div>
        <div className="px-6 py-5 max-h-[80vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
