export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const when = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  });

export const monthYear = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { month: "short", year: "numeric" });

/** Scores pile up near 1.0; show ">99.99%" instead of a misleading "100.00%". */
export const pct = (x: number) =>
  x >= 0.9999 ? ">99.99%" : `${(100 * x).toFixed(x > 0.99 ? 2 : 1)}%`;

export const category = (c: string) => c.replace("_", " ");

export const merchantName = (m: string) => m.replace(/^fraud_/, "");

export type Tier = { label: string; color: string };

/** Three bands around the alert threshold, for color and wording only. */
export function riskTier(score: number, threshold: number): Tier {
  if (score >= threshold) return { label: "High risk", color: "text-risk" };
  if (score >= 0.2) return { label: "Elevated", color: "text-warn" };
  return { label: "Low risk", color: "text-ok" };
}

/** Great-circle distance in km (same formula as the backend's haversine). */
export function km(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = (d: number) => (d * Math.PI) / 180;
  const a = Math.sin(r(lat2 - lat1) / 2) ** 2
    + Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lon2 - lon1) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// How to show each model feature to a person. Anything not listed falls back to the raw number.
const FORMAT: Record<string, (v: number, amt?: number) => string> = {
  amt: money,
  log_amt: (_, amt) => (amt === undefined ? "n/a" : money(amt)), // log(1 + amount) -> the amount
  amt_sum_1h: money, amt_sum_24h: money, amt_sum_7D: money,
  amt_z_card: (v) => `${v.toFixed(1)} σ`,
  amt_ratio_card: (v) => `${v.toFixed(1)}×`,
  secs_since_last: (v) => (v < 3600 ? `${Math.round(v / 60)} min` : `${(v / 3600).toFixed(1)} h`),
  dist_home_km: (v) => `${Math.round(v)} km`,
  dist_prev_km: (v) => `${Math.round(v)} km`,
  speed_kmh: (v) => `${Math.round(v)} km/h`,
  is_new_merchant: (v) => (v ? "yes" : "no"),
  hour: (v) => `${String(v).padStart(2, "0")}:00`,
  dow: (v) => DAYS[v] ?? String(v),
  age: (v) => `${Math.floor(v)} yrs`,
};

export function featureValue(feature: string, v: number | string | null, amt?: number): string {
  if (v === null) return "n/a";
  if (typeof v === "string") return category(v);
  return FORMAT[feature]?.(v, amt) ?? v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
