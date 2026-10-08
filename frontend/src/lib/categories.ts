import {
  ArrowLeftRight,
  BookOpen,
  Bus,
  Clapperboard,
  HeartPulse,
  House,
  type LucideIcon,
  ReceiptText,
  ShoppingBag,
  ShoppingBasket,
  Sparkles,
  UtensilsCrossed,
  Wallet,
} from "lucide-react";

export const CATEGORIES: { key: string; label: string; color: string; icon: LucideIcon }[] = [
  { key: "food", label: "Food", color: "#f59e0b", icon: UtensilsCrossed },
  { key: "groceries", label: "Groceries", color: "#84cc16", icon: ShoppingBasket },
  { key: "travel", label: "Travel", color: "#3b82f6", icon: Bus },
  { key: "shopping", label: "Shopping", color: "#ec4899", icon: ShoppingBag },
  { key: "bills", label: "Bills", color: "#8b5cf6", icon: ReceiptText },
  { key: "rent", label: "Rent", color: "#0ea5e9", icon: House },
  { key: "entertainment", label: "Entertainment", color: "#14b8a6", icon: Clapperboard },
  { key: "health", label: "Health", color: "#ef4444", icon: HeartPulse },
  { key: "education", label: "Education", color: "#06b6d4", icon: BookOpen },
  { key: "transfers", label: "Transfers", color: "#64748b", icon: ArrowLeftRight },
  { key: "income", label: "Income", color: "#10b981", icon: Wallet },
  { key: "other", label: "Other", color: "#94a3b8", icon: Sparkles },
];

export const SPEND_CATEGORIES = CATEGORIES.filter((c) => c.key !== "income");

const BY_KEY = Object.fromEntries(CATEGORIES.map((c) => [c.key, c]));

export function category(key: string) {
  return BY_KEY[key] ?? BY_KEY.other;
}

export const SOURCE_LABEL: Record<string, string> = {
  rule: "Rule",
  ai: "AI",
  you: "You",
  learned: "Learned",
  other: "Unsorted",
};
