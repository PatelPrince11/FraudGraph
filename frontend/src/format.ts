export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const when = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  });

// Two decimals near the top, or every alert would read "100.0%".
export const pct = (x: number) => `${(100 * x).toFixed(x > 0.99 ? 2 : 1)}%`;

export const category = (c: string) => c.replace("_", " ");

const MONEY_FEATURES = new Set(["amt", "amt_sum_1h", "amt_sum_24h", "amt_sum_7D"]);

/** Human-readable value for a model feature. */
export function featureValue(feature: string, v: number | string | null, amt?: number): string {
  if (v === null) return "n/a";
  // log_amt is log(1 + amount): show the dollar amount a person understands.
  if (feature === "log_amt" && amt !== undefined) return money(amt);
  if (MONEY_FEATURES.has(feature) && typeof v === "number") return money(v);
  if (typeof v === "string") return category(v);
  return Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : String(v);
}
