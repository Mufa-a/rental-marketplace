import type { LegalDoc } from "./types";

export const cookies: LegalDoc = {
  slug: "cookies",
  title: "Cookie Policy",
  description: "Which cookies and similar storage Nyumbani actually uses.",
  intro:
    "This page lists what the website actually stores in your browser today. We do not claim any cookie that is not really used.",
  sections: [
    {
      id: "summary",
      heading: "1. Summary",
      body: [
        "The Nyumbani website does not set advertising, marketing or analytics cookies. It stores a sign-in session in your browser’s local storage, which is essential for signing in. There is currently no cookie banner because there are no non-essential cookies to consent to. If we add any, we will ask for your consent where required.",
      ],
    },
    {
      id: "essential",
      heading: "2. Essential: authentication and session",
      body: [
        "After you verify your phone number, the website stores three items in your browser’s local storage so you stay signed in: a short-lived access token (rental_access), a refresh token (rental_refresh) and a small record of your role and phone number (rental_user). They are removed when you sign out. Local storage is a browser storage technology similar to a cookie; we describe it here for transparency.",
        "Staff-only administration pages (the Django admin on the API server) use a session cookie and a CSRF cookie. Ordinary users never receive these.",
      ],
    },
    {
      id: "preferences",
      heading: "3. Preferences",
      body: ["The website does not currently store display or language preferences."],
    },
    {
      id: "analytics",
      heading: "4. Analytics",
      body: ["None. The website does not currently use analytics tools."],
    },
    {
      id: "marketing",
      heading: "5. Marketing and advertising",
      body: ["None. The website does not currently use advertising or marketing cookies or trackers."],
    },
    {
      id: "third-party",
      heading: "6. Third-party resources",
      body: [
        "Some resources are loaded from other companies, which receive your IP address and browser details as any web request does: fonts from Google Fonts on every page, and, only when you open the nearby map, a map library from unpkg and map tiles from MapTiler or OpenStreetMap. We do not set cookies for them; what they do is described in their own policies.",
      ],
    },
    {
      id: "control",
      heading: "7. Your choices",
      body: [
        "You can clear the stored session by signing out or by clearing your browser’s site data. If you block local storage you will not be able to stay signed in.",
      ],
    },
  ],
};
