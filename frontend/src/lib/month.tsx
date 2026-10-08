import { useQuery } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import { api } from "./api";

// The month every page is looking at. It starts at the latest month that has payments.
interface MonthState {
  month: string | null;
  months: string[];
  ready: boolean; // the month list has loaded (it can be empty for a new account)
  error: unknown; // the month list failed to load
  setMonth: (m: string) => void;
}

const MonthContext = createContext<MonthState>({ month: null, months: [], ready: false, error: null, setMonth: () => {} });

export function MonthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({ queryKey: ["months"], queryFn: () => api<string[]>("/api/analytics/months") });
  const months = query.data ?? [];
  const [month, setMonth] = useState<string | null>(null);
  useEffect(() => {
    if (months.length && (!month || !months.includes(month))) setMonth(months[0]);
  }, [months, month]);
  return (
    <MonthContext.Provider value={{ month, months, ready: query.isSuccess, error: query.error, setMonth }}>{children}</MonthContext.Provider>
  );
}

export const useMonth = () => useContext(MonthContext);
