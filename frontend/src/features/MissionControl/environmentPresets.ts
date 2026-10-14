/**
 * Environment presets — anonymous, terrain-class starting points.
 *
 * Each preset is a convenient set of atmospheric parameters for a
 * broad terrain or weather class. The user picks one to fill the
 * visibility and cloud fields; both remain directly editable in the
 * config bar. There is no fixed scenario; the preset is a starting
 * point, not a ceiling, and every parameter can be overridden.
 *
 * The values are typical magnitudes from public meteorological /
 * radiative-transfer references, rounded to defensible figures. They
 * are anonymous by construction: no real place, country, or
 * organization is named.
 */

export type EnvironmentPreset = {
  id: string
  label: string
  visibility_km: number
  cloud_factor: number
}

export const ENVIRONMENT_PRESETS: EnvironmentPreset[] = [
  { id: "arid",         label: "Arid / clear sky",         visibility_km: 20.0, cloud_factor: 0.05 },
  { id: "maritime",     label: "Maritime / open ocean",    visibility_km: 25.0, cloud_factor: 0.55 },
  { id: "canopy",       label: "Dense canopy",             visibility_km: 4.0,  cloud_factor: 0.75 },
  { id: "highland",     label: "Highland / thin air",      visibility_km: 40.0, cloud_factor: 0.35 },
  { id: "coastal-fog",  label: "Coastal fog / valley",     visibility_km: 6.0,  cloud_factor: 0.45 },
  { id: "polar",        label: "Polar / high albedo",      visibility_km: 12.0, cloud_factor: 0.55 },
  { id: "urban",        label: "Urban / mixed aerosol",    visibility_km: 5.0,  cloud_factor: 0.40 },
  { id: "heavy-aerosol",label: "Heavy aerosol / smog",     visibility_km: 1.5,  cloud_factor: 0.65 },
]
