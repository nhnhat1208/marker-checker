import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ThemePreference = 'light' | 'system' | 'dim' | 'dark' | 'dracula'

interface ThemeCtx {
  theme: 'light' | 'dark'          // resolved — what's actually applied (for editors, syntax highlight, etc.)
  preference: ThemePreference       // saved setting
  setPreference: (p: ThemePreference) => void
}

const Ctx = createContext<ThemeCtx>({
  theme: 'light',
  preference: 'system',
  setPreference: () => {},
})

const DARK_PREFS: ThemePreference[] = ['dark', 'dim', 'dracula']

function isDarkPref(pref: ThemePreference): boolean {
  return DARK_PREFS.includes(pref)
}

function resolveOsDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyTheme(pref: ThemePreference) {
  const el = document.documentElement
  // Remove all theme-specific classes
  el.classList.remove('dark', 'dim', 'dracula')

  if (pref === 'system') {
    el.classList.toggle('dark', resolveOsDark())
  } else if (pref === 'dark') {
    el.classList.add('dark')
  } else if (pref === 'dim') {
    el.classList.add('dark', 'dim')
  } else if (pref === 'dracula') {
    el.classList.add('dark', 'dracula')
  }
  // 'light': no classes needed
}

function resolvedTheme(pref: ThemePreference): 'light' | 'dark' {
  if (pref === 'system') return resolveOsDark() ? 'dark' : 'light'
  return isDarkPref(pref) ? 'dark' : 'light'
}

const VALID: ThemePreference[] = ['light', 'system', 'dim', 'dark', 'dracula']

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => {
    const saved = localStorage.getItem('ui-theme') as ThemePreference | null
    const initial: ThemePreference = saved && VALID.includes(saved) ? saved : 'system'
    applyTheme(initial)
    return initial
  })

  // React to OS preference changes when set to 'system'
  useEffect(() => {
    if (preference !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => document.documentElement.classList.toggle('dark', mq.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [preference])

  const setPreference = (next: ThemePreference) => {
    setPreferenceState(next)
    applyTheme(next)
    localStorage.setItem('ui-theme', next)
  }

  return (
    <Ctx.Provider value={{ theme: resolvedTheme(preference), preference, setPreference }}>
      {children}
    </Ctx.Provider>
  )
}

export const useTheme = () => useContext(Ctx)
