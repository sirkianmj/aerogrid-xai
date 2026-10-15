/**
 * The TourContext object, split out of TourProvider.tsx.
 *
 * React Fast Refresh (which oxlint enforces) requires a component file
 * to export only components. A file that exports both a component and
 * a context or a hook breaks Fast Refresh. The context therefore lives
 * here, and both TourProvider.tsx and useTour.ts import it.
 */

import { createContext } from "react"
import type { TourContextValue } from "./tourTypes"

export const TourContext = createContext<TourContextValue | null>(null)
