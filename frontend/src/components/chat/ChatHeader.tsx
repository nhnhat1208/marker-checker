import { useEffect, useRef, useState } from 'react'
import { LogOut, Trash2, ChevronDown, Sun, Moon, Monitor, CloudMoon, Ghost, Check, Languages } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { useTheme, type ThemePreference } from '@/contexts/theme'
import i18n from '@/i18n'
import type { User } from '@/App'

type Props = {
  connected: boolean
  hasMessages: boolean
  user: User
  onClear: () => void
}

/* ── Theme data ── */
const THEME_OPTIONS: { value: ThemePreference; icon: React.ElementType; label: string; desc: string }[] = [
  { value: 'system',  icon: Monitor,   label: 'System',  desc: 'Follow OS' },
  { value: 'light',   icon: Sun,       label: 'Light',   desc: 'Clean white' },
  { value: 'dark',    icon: Moon,      label: 'Dark',    desc: 'Deep zinc' },
  { value: 'dim',     icon: CloudMoon, label: 'Dim',     desc: 'Soft blue-gray' },
  { value: 'dracula', icon: Ghost,     label: 'Dracula', desc: 'Dark purple' },
]

const PREF_ICONS: Record<ThemePreference, React.ElementType> = {
  light: Sun, system: Monitor, dim: CloudMoon, dark: Moon, dracula: Ghost,
}

/* ── Language data ── */
const LANG_OPTIONS = [
  { code: 'vi', flag: '🇻🇳', label: 'Tiếng Việt' },
  { code: 'en', flag: '🇺🇸', label: 'English' },
]

/* ── Theme inline accordion ── */
function ThemeMenuItem() {
  const { preference, setPreference } = useTheme()
  const [expanded, setExpanded] = useState(false)

  const ThemeIcon = PREF_ICONS[preference]
  const currentLabel = THEME_OPTIONS.find(t => t.value === preference)?.label ?? 'Theme'

  return (
    <div className="px-1.5">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className={cn(
          'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
          expanded ? 'bg-muted text-foreground' : 'text-foreground hover:bg-muted/60',
        )}
      >
        <ThemeIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="flex-1 text-left">Theme</span>
        <span className="text-xs text-muted-foreground/50">{currentLabel}</span>
        <ChevronDown className={cn(
          'h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-transform duration-200',
          expanded && 'rotate-180',
        )} />
      </button>

      {expanded && (
        <div className="mt-0.5 space-y-0.5 pb-1">
          {THEME_OPTIONS.map(({ value, icon: Icon, label, desc }) => (
            <button
              key={value}
              type="button"
              onClick={() => { setPreference(value); setExpanded(false) }}
              className={cn(
                'flex w-full items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm transition-colors',
                preference === value
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-foreground hover:bg-muted/60',
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 text-left">{label}</span>
              <span className="text-xs text-muted-foreground/50">{desc}</span>
              {preference === value && <Check className="h-3 w-3 shrink-0 text-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Language inline accordion ── */
function LanguageMenuItem() {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const current = LANG_OPTIONS.find(l => l.code === i18n.language) ?? LANG_OPTIONS[0]

  const changeLang = (code: string) => {
    i18n.changeLanguage(code)
    localStorage.setItem('ui-lang', code)
    setExpanded(false)
  }

  return (
    <div className="px-1.5">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className={cn(
          'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
          expanded ? 'bg-muted text-foreground' : 'text-foreground hover:bg-muted/60',
        )}
      >
        <Languages className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="flex-1 text-left">{t('lang.label')}</span>
        <span className="text-xs text-muted-foreground/50">{current.flag} {current.label}</span>
        <ChevronDown className={cn(
          'h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-transform duration-200',
          expanded && 'rotate-180',
        )} />
      </button>

      {expanded && (
        <div className="mt-0.5 space-y-0.5 pb-1">
          {LANG_OPTIONS.map(({ code, flag, label }) => (
            <button
              key={code}
              type="button"
              onClick={() => changeLang(code)}
              className={cn(
                'flex w-full items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm transition-colors',
                i18n.language === code
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-foreground hover:bg-muted/60',
              )}
            >
              <span className="text-base leading-none">{flag}</span>
              <span className="flex-1 text-left">{label}</span>
              {i18n.language === code && <Check className="h-3 w-3 shrink-0 text-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Profile dropdown ── */
function ProfileMenu({ user }: { user: User }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const initials = (user.name || user.email).charAt(0).toUpperCase()

  return (
    <div ref={ref} className="relative">

      {/* Trigger */}
      <button
        onClick={() => setOpen(v => !v)}
        className={cn(
          'flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors select-none',
          open ? 'bg-muted' : 'hover:bg-muted/60',
        )}>
        {user.avatar_url ? (
          <img src={user.avatar_url} alt={user.name} className="h-7 w-7 rounded-full ring-1 ring-border" />
        ) : (
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {initials}
          </div>
        )}
        <span className="hidden max-w-[110px] truncate text-sm font-medium text-foreground sm:block">
          {user.name || user.email}
        </span>
        <ChevronDown className={cn(
          'h-3.5 w-3.5 text-muted-foreground transition-transform duration-200',
          open && 'rotate-180',
        )} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className={cn(
          'absolute right-0 top-full z-50 mt-1.5 w-64 overflow-visible rounded-xl border border-border bg-background shadow-xl',
          'animate-in fade-in-0 zoom-in-95 slide-in-from-top-2 duration-150',
        )}>

          {/* User info */}
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt={user.name} className="h-9 w-9 shrink-0 rounded-full ring-1 ring-border" />
            ) : (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                {initials}
              </div>
            )}
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">{user.name}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
          </div>

          {/* Settings */}
          <div className="py-1.5 space-y-0.5">
            <ThemeMenuItem />
            <LanguageMenuItem />
            <div className="px-1.5">
              <a href="/auth/logout"
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-red-600 dark:text-red-400 transition-colors hover:bg-red-50 dark:hover:bg-red-950/30">
                <LogOut className="h-3.5 w-3.5" />
                {t('header.sign_out', 'Sign out')}
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Header ── */
export default function ChatHeader({ connected, hasMessages, user, onClear }: Props) {
  const { t } = useTranslation()

  return (
    <header className="relative z-10 shrink-0 border-b border-border bg-background px-5 py-3">
      <div className="mx-auto flex max-w-4xl items-center justify-between">

        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary shadow-sm">
            <span className="select-none text-sm font-bold text-primary-foreground">M</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground leading-tight">Marker Checker</p>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={cn(
                'h-1.5 w-1.5 rounded-full',
                connected ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse',
              )} />
              <span className="text-xs text-muted-foreground">
                {connected ? t('header.status_ready') : t('header.status_connecting')}
              </span>
            </div>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          <button
            onClick={onClear}
            disabled={!hasMessages}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-30">
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t('header.clear_chat')}</span>
          </button>

          <span className="h-4 w-px bg-border" />

          <ProfileMenu user={user} />
        </div>
      </div>
    </header>
  )
}
