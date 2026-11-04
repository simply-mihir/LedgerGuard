import React, { useState } from 'react';

interface CopyButtonProps {
  text: string;
  label?: string;
  className?: string;
}

export function CopyButton({ text, label = 'Copy identifier', className = '' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? 'Copied to clipboard' : label}
      title={copied ? 'Copied!' : label}
      className={`btn-interactive ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0.2rem 0.4rem',
        borderRadius: '6px',
        background: copied ? 'rgba(13, 242, 166, 0.15)' : 'rgba(255, 255, 255, 0.05)',
        border: `1px solid ${copied ? 'rgba(13, 242, 166, 0.35)' : 'rgba(255, 255, 255, 0.08)'}`,
        color: copied ? '#0df2a6' : '#94a3b8',
        fontSize: '0.6875rem',
        fontFamily: 'inherit',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        lineHeight: 1,
      }}
    >
      {copied ? (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
          ✓ <span style={{ fontSize: '0.625rem' }}>Copied</span>
        </span>
      ) : (
        <span>Copy</span>
      )}
    </button>
  );
}
