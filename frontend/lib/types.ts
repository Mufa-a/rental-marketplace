/** Shapes returned by the Django API (see each backend app's serializers.py). */
export type Media = { id: number; url: string; alt_text: string; media_type: string };
export type Amenity = { id: number; name: string; slug: string; icon?: string };

export type PublicProperty = {
  name: string; area: string; city: string; county: string; country: string;
  verification_status: string; landlord_verified: boolean; latitude?: number; longitude?: number;
};

export type PublicListing = {
  id: number; slug: string; path: string; title: string; description: string; unit_type: string;
  monthly_rent: number; security_deposit: number; bedrooms: number; bathrooms: string; floor_area_sqm: number | null;
  furnishing: string; available: boolean; available_from: string | null; availability_confirmed_at: string | null;
  amenity_details: Amenity[]; media: Media[]; distance_km: number | null; property: PublicProperty;
  created_at: string; updated_at: string;
};

export type SearchPage = {
  results: PublicListing[]; next: string | null; previous: string | null; count: number;
  ordering: string; orderings: { value: string; label: string }[];
};

export type LocationSuggestion = { county: string; town: string; estate: string; listings: number; lowest_rent: number };

export type Package = { id: number; name: string; description: string; credits: number; price: number; currency: string; price_per_viewing: number };

export type Payment = {
  id: number; purpose: string; status: "pending" | "successful" | "failed" | "cancelled" | "refunded" | "disputed";
  amount: number; currency: string; credits: number | null; failure_reason: string; provider_receipt: string | null;
  message: string; created_at: string; completed_at: string | null; refunded_at: string | null;
};

export type Wallet = { balance: number; packages: Package[]; conditions: string[]; pending_payment: Payment | null };

export type ViewingSummary = { id: number; scheduled_at: string; status: string; meeting_note: string; completed_at: string | null; reschedule_count: number };

export type Contact = {
  name: string; phone: string; address?: string; area?: string; city?: string; county?: string;
  latitude?: number | null; longitude?: number | null; meeting_note?: string;
};

export type TimelineEvent = { action: string; label: string; by: string; detail: string; at: string };

export type ViewingRequest = {
  id: number; unit: number; unit_title: string; unit_slug: string; unit_path: string; property_name: string; area: string; city: string;
  monthly_rent: number; unit_available: boolean; preferred_times: string[]; note: string; status: string;
  landlord_note: string; responded_at: string | null; cancelled_by: string; cancel_reason: string;
  viewing: ViewingSummary | null; my_role: "tenant" | "landlord" | "admin" | null; my_outcome: string | null;
  contact: Contact | null; created_at: string; timeline?: TimelineEvent[];
};

export type Notification = { id: number; event: string; title: string; message: string; link: string; read: boolean; created_at: string };

export type SessionUser = { id: number; phone_number: string; role: "tenant" | "landlord" | "admin" };
