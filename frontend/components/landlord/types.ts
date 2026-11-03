export type OwnProperty = {
  id: number; name: string; description: string; address_line: string; area: string; city: string; county: string;
  latitude: number | null; longitude: number | null; verification_status: string; is_active: boolean;
};

export type OwnUnit = {
  id: number; property_id: number; unit_number: string; slug: string; title: string; description: string; unit_type: string;
  monthly_rent: number; security_deposit: number; bedrooms: number; bathrooms: string; floor_area_sqm: number | null;
  furnishing: string; available: boolean; availability_confirmed_at: string | null; available_from: string | null;
  is_published: boolean; moderation_hold: boolean; moderation_status: string; moderation_note: string;
  amenities: number[]; media: { id: number; url: string; alt_text: string }[];
};

export type UnitStats = {
  unit_id: number; title: string; property: string; visible_in_search: boolean; moderation_status: string;
  views_7d: number; views_30d: number; saves: number; requests: number; pending: number; approved: number; completed: number; rented: number;
};

export type Stats = { totals: Omit<UnitStats, "unit_id" | "title" | "property" | "visible_in_search" | "moderation_status"> & { request_rate: number | null }; units: UnitStats[] };

export type Fee = { id: number; viewing_id: number; unit_title: string; amount: number; currency: string; monthly_rent: number | null; status: string; due_at: string | null; paid_at: string | null };
