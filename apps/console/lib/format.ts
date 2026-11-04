/**
 * Formatting utilities for financial currency (INR paise), dates, times, and identifiers.
 */

/**
 * Format integer paise minor units into standard Indian Rupee representation (₹0.00).
 */
export function formatINR(paise: number): string {
  const isNegative = paise < 0;
  const absPaise = Math.abs(paise);
  const rupees = (absPaise / 100).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${isNegative ? '-' : ''}₹${rupees}`;
}

/**
 * Format numeric counts with locale commas.
 */
export function formatNumber(value: number): string {
  return value.toLocaleString('en-IN');
}

/**
 * Format ISO timestamp into short locale time (e.g. 10:28:15 AM).
 */
export function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '—';
  }
}

/**
 * Format ISO timestamp into standard full date and time.
 */
export function formatDateTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '—';
  }
}

/**
 * Calculate short relative elapsed time string (e.g. "12s ago", "4m ago").
 */
export function formatRelativeAge(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
    if (seconds < 5) return 'just now';
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  } catch {
    return '—';
  }
}

/**
 * Truncate UUID or hash for dense display.
 */
export function truncateId(id: string, startChars: number = 8, endChars: number = 0): string {
  if (!id) return '—';
  if (id.length <= startChars + endChars) return id;
  if (endChars > 0) {
    return `${id.slice(0, startChars)}...${id.slice(-endChars)}`;
  }
  return `${id.slice(0, startChars)}...`;
}
