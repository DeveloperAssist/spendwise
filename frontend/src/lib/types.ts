// The shapes the API sends back (see backend/src/spendwise/api/schemas.py).

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface Transaction {
  id: number;
  date: string;
  merchant: string;
  description: string;
  amount: number;
  kind: "debit" | "credit";
  category: string;
  category_source: "rule" | "ai" | "you" | "learned" | "other";
  note: string | null;
  import_id: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface BudgetStatus {
  category: string;
  spent: number;
  limit: number;
  used: number;
  status: "ok" | "close" | "over";
}

export interface Dashboard {
  month: string;
  summary: {
    spent: number;
    income: number;
    saved: number;
    savings_rate: number | null;
    payments: number;
    daily_average: number;
    forecast: number | null;
    days_left: number;
    by_category: Record<string, number>;
    top_merchants: { merchant: string; spent: number; payments: number }[];
  };
  change: Record<string, number | null>;
  budgets: BudgetStatus[];
  trend: { month: string; spent: number; income: number }[];
  daily: { date: string; spent: number }[];
}

export interface ImportResult {
  id: number;
  filename: string;
  added: number;
  duplicates: number;
  skipped: number;
  created_at: string;
  skipped_rows: { line: number; reason: string }[];
  categorized_by: Record<string, number>;
}

export interface Subscription {
  merchant: string;
  category: string;
  type: "bill" | "subscription";
  amount: number;
  times: number;
  last_paid: string;
  next_expected: string;
}

export interface Unusual {
  id: number;
  date: string;
  merchant: string;
  category: string;
  amount: number;
  typical: number;
  times_usual: number;
}

export interface ChatStep {
  tool: string;
  args: Record<string, unknown>;
  ok: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  steps?: ChatStep[];
}
