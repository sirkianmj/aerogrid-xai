import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import App from "./App.tsx"

// Respect the OS theme. Tokens default to light; when the system asks
// for dark, apply the `.dark` class and keep it in sync as the OS
// preference changes.
const mql = window.matchMedia("(prefers-color-scheme: dark)")
const applyTheme = (isDark: boolean) => {
  document.documentElement.classList.toggle("dark", isDark)
}
applyTheme(mql.matches)
mql.addEventListener("change", (e) => applyTheme(e.matches))

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
