import React, { useEffect, useRef } from 'react';

interface SheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  width?: string;
}

export function Sheet({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  width = '580px',
}: SheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previouslyFocusedElement.current = document.activeElement as HTMLElement;
      // Lock body scroll
      document.body.style.overflow = 'hidden';

      // Focus close button or sheet
      const focusable = sheetRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable) {
        focusable.focus();
      }

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          onClose();
        }
      };

      window.addEventListener('keydown', handleKeyDown);
      return () => {
        window.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = '';
        previouslyFocusedElement.current?.focus();
      };
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(5, 7, 12, 0.70)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          animation: 'fade-in 0.2s ease-out',
        }}
      />

      {/* Sheet Panel */}
      <aside
        ref={sheetRef}
        className="signal-sheet-panel"
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: width,
          height: '100%',
          background: 'rgba(11, 15, 25, 0.92)',
          backdropFilter: 'blur(32px)',
          WebkitBackdropFilter: 'blur(32px)',
          borderLeft: '1px solid rgba(255, 255, 255, 0.12)',
          borderTopLeftRadius: 'var(--radius-primary, 28px)',
          borderBottomLeftRadius: 'var(--radius-primary, 28px)',
          boxShadow: '-12px 0 48px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.12)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 201,
          animation: 'slide-in-right 0.28s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.5rem 1.75rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '1rem',
            background: 'rgba(14, 20, 34, 0.85)',
            borderTopLeftRadius: 'var(--radius-primary, 28px)',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: '1.1875rem',
                fontWeight: 700,
                color: '#F8FAFC',
                letterSpacing: '-0.02em',
              }}
            >
              {title}
            </h2>
            {subtitle && (
              <div
                style={{
                  fontSize: '0.8125rem',
                  color: '#94A3B8',
                  marginTop: '0.25rem',
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close sheet"
            className="btn-interactive"
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-control, 14px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              color: '#94A3B8',
              cursor: 'pointer',
              flexShrink: 0,
              transition: 'all 0.18s ease',
            }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.75rem',
          }}
        >
          {children}
        </div>
      </aside>
    </div>
  );
}
