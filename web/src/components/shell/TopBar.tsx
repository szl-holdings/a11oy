import { useState, useRef, useEffect } from 'react';
import { useOrg } from '../../context/OrgContext';
import type { OrgId } from '../../context/OrgContext';
import { ChevronDown } from 'lucide-react';

export function TopBar() {
  const { currentOrg, setOrg } = useOrg();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const orgs: { id: OrgId; name: string }[] = [
    { id: 'szl', name: 'a11oy' },
    { id: 'acme', name: 'Acme Industries' },
    { id: 'northwind', name: 'Northwind Labs' }
  ];

  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      setIsOpen(false);
      triggerRef.current?.focus();
    }
  }

  function handleOrgSelect(id: OrgId) {
    setOrg(id);
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  return (
    <header className="h-14 border-b border-[var(--color-a11oy-border)] bg-[var(--color-a11oy-deep)] flex items-center justify-between px-6 shrink-0 z-30 sticky top-0">
      <div className="flex items-center gap-5">
        <div className="flex items-baseline gap-2">
          <span className="font-display font-semibold text-lg tracking-tight text-[var(--color-a11oy-text)]">
            A<span className="font-mono text-[var(--color-a11oy-blue)] font-bold">11</span>oy
          </span>
        </div>

        <div className="h-4 w-px bg-[var(--color-a11oy-border)]" aria-hidden="true"></div>

        <div className="relative" ref={menuRef} onKeyDown={handleKeyDown}>
          <button
            ref={triggerRef}
            type="button"
            onClick={() => setIsOpen(prev => !prev)}
            aria-haspopup="listbox"
            aria-expanded={isOpen}
            aria-label={`Current organization: ${orgs.find(o => o.id === currentOrg)?.name}. Change organization`}
            className="flex items-center gap-2 text-sm text-[var(--color-a11oy-text-sub)] hover:text-[var(--color-a11oy-text)] transition-colors cursor-pointer"
          >
            <span className="font-medium">{orgs.find(o => o.id === currentOrg)?.name}</span>
            <ChevronDown className="w-3.5 h-3.5 opacity-50" aria-hidden="true" />
          </button>

          {isOpen && (
            <ul
              role="listbox"
              aria-label="Select organization"
              className="absolute top-full left-0 mt-2 w-48 bg-[var(--color-a11oy-card)] border border-[var(--color-a11oy-border)] rounded shadow-xl z-50 py-1"
            >
              {orgs.map(org => (
                <li key={org.id} role="option" aria-selected={currentOrg === org.id}>
                  <button
                    type="button"
                    onClick={() => handleOrgSelect(org.id)}
                    className={`w-full text-left px-4 py-2 text-sm transition-colors ${currentOrg === org.id ? 'bg-[var(--color-a11oy-surface)] text-[var(--color-a11oy-blue)]' : 'text-[var(--color-a11oy-text-sub)] hover:bg-[var(--color-a11oy-surface)] hover:text-[var(--color-a11oy-text)]'}`}
                  >
                    {org.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-a11oy-blue)] animate-pulse" aria-hidden="true" />
        <span className="text-[11px] font-mono" style={{ color: 'var(--color-a11oy-text-ghost)', letterSpacing: '0.04em' }}>
          Governed Environment
        </span>
      </div>
    </header>
  );
}
