import { useEffect, useId, useRef, useState } from 'react';

/* Founder ContactModal (szl-console.css .scrim/.dialog-layer/.dialog/.copy-row/.close-btn):
   role="dialog" + aria-modal, labelled title, focus moves in and is trapped, Escape or a
   scrim click closes, focus returns to the trigger, 44px close target. Works uncontrolled
   (trigger) or controlled (isOpen + onClose, as conduit-landing calls it). */

interface ContactModalProps {
  type?: string;
  app?: string;
  trigger?: React.ReactNode;
  isOpen?: boolean;
  onClose?: () => void;
  subtitle?: string;
}

const CONTACT = 'stephen@szlholdings.com';
const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function ContactModal({ type = 'demo', app = 'amaru', trigger, isOpen, onClose, subtitle }: ContactModalProps) {
  const controlled = typeof isOpen === 'boolean';
  const [innerOpen, setInnerOpen] = useState(false);
  const open = controlled ? isOpen : innerOpen;
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const closeRef = useRef<() => void>(() => {});
  closeRef.current = () => {
    if (!controlled) setInnerOpen(false);
    onClose?.();
  };

  useEffect(() => {
    if (!open) return undefined;
    const returnTo = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    panel?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeRef.current();
        return;
      }
      if (e.key !== 'Tab' || !panel) return;
      const items = panel.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      returnTo?.focus?.();
    };
  }, [open]);

  const title = type === 'demo' ? 'Request a Demo' : 'Request Access';

  return (
    <>
      {trigger && (
        <span className="inline-flex cursor-pointer" onClick={() => setInnerOpen(true)}>
          {trigger}
        </span>
      )}
      {open && (
        <>
          <div className="scrim" aria-hidden="true" />
          <div
            className="dialog-layer"
            onMouseDown={(e) => {
              if (e.target === e.currentTarget) closeRef.current();
            }}
          >
            <div ref={panelRef} role="dialog" aria-modal="true" aria-labelledby={titleId} className="dialog">
              <button type="button" onClick={() => closeRef.current()} aria-label="Close" className="close-btn absolute top-4 right-4 m-0">
                ✕
              </button>
              <p className="eyebrow m-0 pr-12 text-ink-sub">{subtitle ?? 'Contact'}</p>
              <h2 id={titleId} className="dialog__title pr-12">{title}</h2>
              <p className="dialog__body">Contact us for {app} access.</p>
              <div className="copy-row">
                <a href={`mailto:${CONTACT}`} className="copy-row__value">{CONTACT}</a>
              </div>
              <div className="dialog__actions">
                <button type="button" onClick={() => closeRef.current()} className="btn btn-secondary">
                  Close
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
