/**
 * Theme preference: "auto" (follow OS), "light", or "dark".
 *
 * Persisted under `aerogrid.theme` in localStorage. Applying a
 * preference toggles the `.dark` class on <html>, which the token
 * stylesheet keys off. When the preference is "auto", we listen to
 * the OS `prefers-color-scheme` media query and re-apply on change.
 */

export type ThemePref = "auto" | "light" | "dark"

export const THEME_KEY = "aerogrid.theme"

const MQL = "(prefers-color-scheme: dark)"

export function readThemePref(): ThemePref {
  if (typeof window === "undefined") return "auto"
  const v = window.localStorage.getItem(THEME_KEY)
  return v === "light" || v === "dark" ? v : "auto"
}

export function applyTheme(pref: ThemePref): void {
  if (typeof window === "undefined") return
  const osDark = window.matchMedia(MQL).matches
  const isDark = pref === "dark" || (pref === "auto" && osDark)
  document.documentElement.classList.toggle("dark", isDark)
}

export function setThemePref(pref: ThemePref): void {
  window.localStorage.setItem(THEME_KEY, pref)
  applyTheme(pref)
  window.dispatchEvent(new Event("aerogrid:theme-change"))
}

/** Install the OS-preference listener. Call once at boot. */
export function installThemeListener(): void {
  const mql = window.matchMedia(MQL)
  mql.addEventListener("change", () => {
    if (readThemePref() === "auto") applyTheme("auto")
  })
  applyTheme(readThemePref())
}
