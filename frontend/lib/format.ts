export const money = (amount: number | null | undefined, currency = "KES") =>
  amount == null ? "—" : `${currency === "KES" ? "KSh" : currency} ${Math.round(amount).toLocaleString("en-KE")}`;

export const plural = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;

export const titleCase = (value: string) => value.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());

export const UNIT_TYPES: Record<string, string> = {
  bedsitter: "Bedsitter", studio: "Studio", apartment: "Apartment", house: "House", maisonette: "Maisonette", room: "Room",
};
export const FURNISHING: Record<string, string> = { unfurnished: "Unfurnished", semi_furnished: "Semi-furnished", furnished: "Furnished" };

export const bedroomsLabel = (bedrooms: number, unitType?: string) =>
  bedrooms === 0 ? (unitType === "studio" ? "Studio" : "Bedsitter") : plural(bedrooms, "bedroom");

export const bathroomsLabel = (bathrooms: string | number) => {
  const n = Number(bathrooms);
  return `${Number.isInteger(n) ? n : n.toFixed(1)} bath${n === 1 ? "" : "s"}`;
};

export const dateTime = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString("en-KE", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "";

export const date = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" }) : "";

export const relative = (value: string) => {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${days} d ago` : date(value);
};

/** Kenyan numbers for display: +254712345678 -> 0712 345 678 */
export const phone = (value: string) => {
  const local = value.replace(/^\+254/, "0");
  return local.length === 10 ? `${local.slice(0, 4)} ${local.slice(4, 7)} ${local.slice(7)}` : value;
};
