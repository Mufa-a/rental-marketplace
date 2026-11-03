export type Filters = {
  q: string; county: string; town: string; estate: string; min_rent: string; max_rent: string; bedrooms: string;
  bathrooms: string; unit_type: string; furnishing: string; amenities: string; move_in_date: string; verified_only: string; ordering: string;
};

export const EMPTY_FILTERS: Filters = {
  q: "", county: "", town: "", estate: "", min_rent: "", max_rent: "", bedrooms: "", bathrooms: "", unit_type: "",
  furnishing: "", amenities: "", move_in_date: "", verified_only: "", ordering: "",
};

export const FILTER_KEYS = Object.keys(EMPTY_FILTERS) as (keyof Filters)[];

export function filtersFrom(params: Record<string, string | string[] | undefined> | URLSearchParams): Filters {
  const get = (key: string) => {
    const value = params instanceof URLSearchParams ? params.get(key) : params[key];
    return (Array.isArray(value) ? value[0] : value ?? "").slice(0, 100);
  };
  return Object.fromEntries(FILTER_KEYS.map((key) => [key, get(key)])) as Filters;
}

export function queryString(filters: Partial<Filters>, extra: Record<string, string> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value && String(value).trim()) query.set(key, String(value).trim());
  for (const [key, value] of Object.entries(extra)) if (value) query.set(key, value);
  return query.toString();
}

export const activeFilterCount = (filters: Filters) => FILTER_KEYS.filter((key) => key !== "ordering" && filters[key]).length;

/** "south-b" -> "south b" for location landing pages. */
export const unslug = (value: string) => decodeURIComponent(value).replace(/-/g, " ").trim();
export const slug = (value: string) => value.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
