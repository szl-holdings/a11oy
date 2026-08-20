import { useState } from 'react';

interface ContactModalProps {
  type?: string;
  app?: string;
  trigger: React.ReactNode;
}

export function ContactModal({ type = 'demo', app = 'amaru', trigger }: ContactModalProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <span onClick={() => setOpen(true)} style={{ cursor: 'pointer' }}>{trigger}</span>
      {open && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.7)',
        }} onClick={() => setOpen(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{
            background: '#1a1a1a', borderRadius: 12, padding: 32,
            border: '1px solid rgba(201,183,135,0.2)', maxWidth: 480, width: '90%',
          }}>
            <h2 style={{ margin: '0 0 16px', fontSize: 20, color: '#f5f5f5' }}>
              Request {type === 'demo' ? 'a Demo' : 'Access'}
            </h2>
            <p style={{ color: '#888', fontSize: 14, margin: '0 0 20px' }}>
              Contact us at <a href="mailto:stephen@szlholdings.com" style={{ color: '#c9b787' }}>stephen@szlholdings.com</a> for {app} access.
            </p>
            <button onClick={() => setOpen(false)} style={{
              background: '#c9b787', color: '#0a0a0a', border: 'none',
              padding: '10px 20px', borderRadius: 6, cursor: 'pointer', fontWeight: 500,
            }}>
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
