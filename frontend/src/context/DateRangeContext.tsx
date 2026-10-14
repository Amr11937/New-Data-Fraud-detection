/**
 * One date range shared by every page that has a date filter, so picking a range on
 * the Executive summary carries over to Subscribers (and back).
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { DateRange } from '@/types';

interface DateRangeState {
  range: DateRange;
  setRange: (range: DateRange) => void;
}

const DateRangeContext = createContext<DateRangeState | null>(null);

export function DateRangeProvider({ children }: { children: ReactNode }) {
  const [range, setRange] = useState<DateRange>({ dateFrom: null, dateTo: null });
  const value = useMemo(() => ({ range, setRange }), [range]);
  return <DateRangeContext.Provider value={value}>{children}</DateRangeContext.Provider>;
}

export function useDateRange(): DateRangeState {
  const ctx = useContext(DateRangeContext);
  if (!ctx) throw new Error('useDateRange must be used inside DateRangeProvider');
  return ctx;
}
