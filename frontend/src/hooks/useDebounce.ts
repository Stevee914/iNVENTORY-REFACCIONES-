import { useEffect, useState } from 'react';

/**
 * Delays updating the returned value until the input has stopped
 * changing for `delay` milliseconds.  Use this to avoid firing an
 * API request on every keystroke when the user is typing a search term.
 */
export function useDebounce<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debounced;
}
