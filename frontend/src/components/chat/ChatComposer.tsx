import { useEffect, useRef, useState } from 'react'
import { Send, ChevronDown, ChevronRight, Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import ReactCodeMirror from '@uiw/react-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { json } from '@codemirror/lang-json'
import { githubLight, githubDark } from '@uiw/codemirror-theme-github'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { CodeFormat, StructuredRequestPayload } from '@/lib/chatTypes'
import { cn } from '@/lib/utils'
import { useTheme } from '@/contexts/theme'

const DRAFT_STORAGE_KEY = 'marker-checker:chat-composer-draft-v2'

// Placeholders loaded from i18n — see PLACEHOLDERS usage in the component body

/* ── Slash commands ── */
type SlashCommand = {
  cmd: string
  args?: string
  desc: string
  category: 'General' | 'Requests' | 'Approvals'
}

const COMMANDS: SlashCommand[] = [
  { cmd: '/help',        desc: 'Show all available commands',               category: 'General'   },
  { cmd: '/mypending',   desc: 'List your active requests',                 category: 'Requests'  },
  { cmd: '/status',      args: 'REQ-XXXX',            desc: 'View request status & details',        category: 'Requests'  },
  { cmd: '/history',     args: 'REQ-XXXX',            desc: 'Full event timeline of a request',     category: 'Requests'  },
  { cmd: '/search',      args: '<query>',              desc: 'Search requests by target name',       category: 'Requests'  },
  { cmd: '/confirm',     desc: 'Submit your pending draft',                  category: 'Requests'  },
  { cmd: '/discard',     desc: 'Cancel your pending draft',                  category: 'Requests'  },
  { cmd: '/resubmit',    args: 'REQ-XXXX <message>',  desc: 'Revise & resubmit after need-info',    category: 'Requests'  },
  { cmd: '/myapprovals', desc: 'List requests waiting for your approval',   category: 'Approvals' },
  { cmd: '/approve',     args: 'REQ-XXXX [note]',     desc: 'Approve a request',                    category: 'Approvals' },
  { cmd: '/reject',      args: 'REQ-XXXX [reason]',   desc: 'Reject a request',                     category: 'Approvals' },
  { cmd: '/needinfo',    args: 'REQ-XXXX [question]', desc: 'Ask requester for more information',   category: 'Approvals' },
  { cmd: '/cancel',      args: 'REQ-XXXX [note]',     desc: 'Cancel a request',                     category: 'Approvals' },
]

const CATEGORY_ORDER: SlashCommand['category'][] = ['General', 'Requests', 'Approvals']

/* ── Editor language ── */
type EditorLanguage =
  | 'yaml' | 'json'
  | 'javascript' | 'typescript' | 'python'
  | 'bash' | 'go' | 'sql' | 'rust'
  | 'html' | 'css' | 'toml' | 'text'

const LANGUAGE_GROUPS: { label: string; langs: { value: EditorLanguage; label: string }[] }[] = [
  {
    label: 'Data / Config',
    langs: [
      { value: 'yaml',       label: 'YAML'       },
      { value: 'json',       label: 'JSON'       },
      { value: 'toml',       label: 'TOML'       },
    ],
  },
  {
    label: 'Code',
    langs: [
      { value: 'javascript', label: 'JavaScript' },
      { value: 'typescript', label: 'TypeScript' },
      { value: 'python',     label: 'Python'     },
      { value: 'bash',       label: 'Bash'       },
      { value: 'go',         label: 'Go'         },
      { value: 'rust',       label: 'Rust'       },
      { value: 'sql',        label: 'SQL'        },
    ],
  },
  {
    label: 'Web',
    langs: [
      { value: 'html',       label: 'HTML'       },
      { value: 'css',        label: 'CSS'        },
    ],
  },
  {
    label: 'Other',
    langs: [
      { value: 'text',       label: 'Plain text' },
    ],
  },
]

function toCodeFormat(lang: EditorLanguage): CodeFormat {
  if (lang === 'yaml') return 'yaml'
  if (lang === 'json') return 'json'
  return 'text'
}

function getExtension(lang: EditorLanguage) {
  if (lang === 'yaml') return [yaml()]
  if (lang === 'json') return [json()]
  return []
}

/* ── Cascading language picker ── */
function LanguagePicker({ value, onChange }: { value: EditorLanguage; onChange: (l: EditorLanguage) => void }) {
  const [open, setOpen] = useState(false)
  const [hoveredGroup, setHoveredGroup] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) { setOpen(false); setHoveredGroup(null) }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  useEffect(() => () => clearTimeout(hideTimer.current), [])

  const showGroup = (label: string) => { clearTimeout(hideTimer.current); setHoveredGroup(label) }
  const scheduleHide = () => { hideTimer.current = setTimeout(() => setHoveredGroup(null), 150) }
  const cancelHide   = () => { clearTimeout(hideTimer.current) }

  const currentLabel = LANGUAGE_GROUPS.flatMap(g => g.langs).find(l => l.value === value)?.label ?? value

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => { setOpen(v => !v); setHoveredGroup(null) }}
        className={cn(
          'flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
          'border-border hover:bg-muted focus:outline-none',
          open && 'bg-muted',
        )}>
        <span className="font-mono">{currentLabel}</span>
        <ChevronDown className={cn('h-3 w-3 text-muted-foreground transition-transform duration-150', open && 'rotate-180')} />
      </button>

      {open && (
        <div className={cn(
          'absolute bottom-full left-0 z-50 mb-1.5 min-w-[9rem] py-1',
          'rounded-xl border border-border bg-background shadow-2xl',
          'animate-in fade-in-0 slide-in-from-bottom-2 duration-150',
        )}>
          {LANGUAGE_GROUPS.map(group => (
            <div
              key={group.label}
              className="relative"
              onMouseEnter={() => showGroup(group.label)}
              onMouseLeave={scheduleHide}>
              <button
                type="button"
                className={cn(
                  'flex w-full items-center justify-between gap-4 whitespace-nowrap px-3 py-1.5 text-xs transition-colors',
                  hoveredGroup === group.label
                    ? 'bg-muted text-foreground font-medium'
                    : 'text-muted-foreground hover:text-foreground',
                )}>
                {group.label}
                <ChevronRight className="h-3 w-3 shrink-0 opacity-40" />
              </button>
              {hoveredGroup === group.label && (
                <div
                  onMouseEnter={cancelHide}
                  onMouseLeave={scheduleHide}
                  className={cn(
                    'absolute left-full top-0 z-50 min-w-[8rem] max-h-56 overflow-y-auto py-1',
                    'rounded-xl border border-border bg-background shadow-2xl',
                    'animate-in fade-in-0 slide-in-from-left-1 duration-100',
                  )}>
                  {group.langs.map(lang => (
                    <button
                      key={lang.value}
                      type="button"
                      onMouseDown={e => { e.preventDefault(); onChange(lang.value); setOpen(false); setHoveredGroup(null) }}
                      className={cn(
                        'flex w-full items-center justify-between gap-4 whitespace-nowrap px-3 py-1.5 text-xs transition-colors',
                        value === lang.value
                          ? 'text-primary font-semibold'
                          : 'text-foreground hover:bg-muted/60',
                      )}>
                      {lang.label}
                      {value === lang.value && <Check className="h-3 w-3 shrink-0 text-primary" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Command picker popup ── */
function CommandPicker({
  query, activeIdx, onSelect,
}: {
  query: string
  activeIdx: number
  onSelect: (cmd: SlashCommand) => void
}) {
  const activeRef = useRef<HTMLButtonElement>(null)
  const filtered = COMMANDS.filter(c => c.cmd.slice(1).startsWith(query.toLowerCase()))

  useEffect(() => { activeRef.current?.scrollIntoView({ block: 'nearest' }) }, [activeIdx])

  if (!filtered.length) return null

  const grouped = CATEGORY_ORDER.reduce<Record<string, SlashCommand[]>>((acc, cat) => {
    const items = filtered.filter(c => c.category === cat)
    if (items.length) acc[cat] = items
    return acc
  }, {})

  let globalIdx = 0

  return (
    <div className={cn(
      'absolute bottom-full left-0 right-0 z-50 mb-2 max-h-72 overflow-y-auto',
      'rounded-xl border border-border bg-background shadow-2xl',
      'animate-in fade-in-0 slide-in-from-bottom-2 duration-150',
    )}>
      {Object.entries(grouped).map(([cat, cmds]) => (
        <div key={cat}>
          <div className="sticky top-0 z-10 bg-background/95 px-3 py-1.5 backdrop-blur-sm">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{cat}</span>
          </div>
          {cmds.map(cmd => {
            const idx = globalIdx++
            const isActive = idx === activeIdx
            return (
              <button
                key={cmd.cmd}
                ref={isActive ? activeRef : undefined}
                onMouseDown={e => { e.preventDefault(); onSelect(cmd) }}
                className={cn(
                  'flex w-full items-center gap-2.5 px-3 py-1.5 text-left transition-colors',
                  isActive ? 'bg-muted' : 'hover:bg-muted/50',
                )}>
                <span className="w-24 shrink-0 font-mono text-xs font-semibold text-primary">{cmd.cmd}</span>
                {cmd.args && (
                  <span className="shrink-0 font-mono text-[11px] text-muted-foreground/60">{cmd.args}</span>
                )}
                <span className="ml-auto truncate text-[11px] text-muted-foreground">{cmd.desc}</span>
              </button>
            )
          })}
        </div>
      ))}
      <div className="sticky bottom-0 flex items-center gap-3 border-t border-border bg-background/95 px-3 py-1.5 backdrop-blur-sm">
        {[['↑↓', 'navigate'], ['↵', 'select'], ['Esc', 'close']].map(([key, hint]) => (
          <span key={key} className="text-[10px] text-muted-foreground/60">
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{key}</kbd>{' '}{hint}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ── Code editor with CodeMirror ── */
function CodeEditor({
  value, onChange, label, tone, language,
}: {
  value: string
  onChange: (v: string) => void
  label: string
  tone: 'before' | 'after'
  language: EditorLanguage
}) {
  const { theme } = useTheme()

  return (
    <div className={cn(
      'flex-1 min-w-0 overflow-hidden rounded-xl border',
      'border-border',
    )}>
      <div className={cn(
        'border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest select-none',
        tone === 'before'
          ? 'border-rose-100 bg-rose-50 text-rose-600 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-400'
          : 'border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-400',
      )}>
        {label}
      </div>
      <ReactCodeMirror
        value={value}
        onChange={(val: string) => onChange(val)}
        theme={theme === 'dark' ? githubDark : githubLight}
        extensions={getExtension(language)}
        minHeight="5rem"
        maxHeight="10rem"
        placeholder={language === 'text' ? 'Plain text here…' : `# ${language} here…`}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          dropCursor: true,
          highlightActiveLine: true,
          highlightSelectionMatches: false,
          bracketMatching: true,
          closeBrackets: true,
          autocompletion: false,
        }}
        style={{ fontSize: '12px' }}
      />
    </div>
  )
}

/* ── Main composer ── */
type ComposerTab = 'message' | 'request'

type Props = {
  connected: boolean
  onSend: (payload: string | StructuredRequestPayload) => void
  fillText?: string
  onFillConsumed?: () => void
}

export default function ChatComposer({ connected, onSend, fillText, onFillConsumed }: Props) {
  const { t } = useTranslation()
  const placeholders = t('composer.placeholders', { returnObjects: true }) as string[]
  const [tab, setTab]               = useState<ComposerTab>('message')
  const [text, setText]             = useState('')
  const [approver, setApprover]     = useState('')
  const [before, setBefore]         = useState('')
  const [after, setAfter]           = useState('')
  const [language, setLanguage]     = useState<EditorLanguage>('yaml')
  const [placeholderIdx, setPlaceholderIdx] = useState(0)
  const [pickerIdx, setPickerIdx]   = useState(0)
  const textRef = useRef<HTMLTextAreaElement>(null)

  // Slash command picker (message tab only)
  const slashMatch   = tab === 'message' ? text.match(/^\/(\S*)$/) : null
  const showPicker   = Boolean(slashMatch && connected)
  const pickerQuery  = slashMatch ? slashMatch[1] : ''
  const filteredCmds = COMMANDS.filter(c => c.cmd.slice(1).startsWith(pickerQuery.toLowerCase()))

  useEffect(() => { setPickerIdx(0) }, [pickerQuery])

  // Rotating placeholder
  useEffect(() => {
    if (text) return
    const timer = setInterval(() => setPlaceholderIdx(i => (i + 1) % placeholders.length), 3000)
    return () => clearInterval(timer)
  }, [text, placeholders.length])

  // Restore draft
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(DRAFT_STORAGE_KEY)
      if (!stored) return
      const p = JSON.parse(stored) as Partial<{
        tab: ComposerTab; text: string; approver: string; before: string; after: string; language: EditorLanguage
      }>
      if (p.tab === 'message' || p.tab === 'request') setTab(p.tab)
      setText(typeof p.text === 'string' ? p.text : '')
      setApprover(typeof p.approver === 'string' ? p.approver : '')
      setBefore(typeof p.before === 'string' ? p.before : '')
      setAfter(typeof p.after === 'string' ? p.after : '')
      if (p.language) setLanguage(p.language)
    } catch { window.localStorage.removeItem(DRAFT_STORAGE_KEY) }
  }, [])

  // Consume external fill text (from empty-state examples)
  useEffect(() => {
    if (!fillText) return
    setText(fillText)
    setTab('message')
    onFillConsumed?.()
    setTimeout(() => {
      if (textRef.current) {
        textRef.current.style.height = 'auto'
        textRef.current.style.height = `${Math.min(textRef.current.scrollHeight, 160)}px`
        textRef.current.focus()
      }
    }, 0)
  }, [fillText, onFillConsumed])

  // Persist draft
  useEffect(() => {
    if (!text && !approver && !before && !after) { window.localStorage.removeItem(DRAFT_STORAGE_KEY); return }
    window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify({ tab, text, approver, before, after, language }))
  }, [after, approver, before, language, tab, text])

  const canSend = connected && (
    tab === 'message'
      ? Boolean(text.trim())
      : Boolean(text.trim() || before.trim() || after.trim())
  )

  const selectCommand = (cmd: SlashCommand) => {
    if (cmd.args) {
      setText(cmd.cmd + ' ')
      setTimeout(() => textRef.current?.focus(), 0)
    } else {
      onSend(cmd.cmd)
      setText('')
    }
    setPickerIdx(0)
  }

  const submit = () => {
    if (!canSend) return
    if (tab === 'message') {
      const trimmed = text.trim()
      if (!trimmed) return
      onSend(trimmed)
    } else {
      const fmt = toCodeFormat(language)
      onSend({
        mode: 'config_change',
        request_format: 'text',
        request: text,
        approver: approver.trim(),
        before: { enabled: Boolean(before.trim()), format: fmt, value: before.replace(/\r\n/g, '\n') },
        after:  { enabled: Boolean(after.trim()),  format: fmt, value: after.replace(/\r\n/g, '\n') },
      } satisfies StructuredRequestPayload)
    }
    setText(''); setApprover(''); setBefore(''); setAfter('')
    window.localStorage?.removeItem(DRAFT_STORAGE_KEY)
    if (textRef.current) { textRef.current.style.height = 'auto'; textRef.current.focus() }
  }

  const handleTextKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showPicker && filteredCmds.length > 0) {
      if (e.key === 'ArrowDown')  { e.preventDefault(); setPickerIdx(i => Math.min(i + 1, filteredCmds.length - 1)); return }
      if (e.key === 'ArrowUp')    { e.preventDefault(); setPickerIdx(i => Math.max(i - 1, 0)); return }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault()
        if (filteredCmds[pickerIdx]) selectCommand(filteredCmds[pickerIdx])
        return
      }
      if (e.key === 'Escape') { e.preventDefault(); setText(''); return }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
  }

  return (
    <div className="shrink-0 border-t border-border bg-background px-3 pb-3 pt-2.5 sm:px-4 sm:pb-4 sm:pt-3">
      <div className="mx-auto max-w-3xl">
        <div className="relative">

          {showPicker && (
            <CommandPicker query={pickerQuery} activeIdx={pickerIdx} onSelect={selectCommand} />
          )}

          <div className={cn(
            'overflow-hidden rounded-2xl border bg-background shadow-lg transition-all',
            'focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10',
            connected ? 'border-border/80' : 'border-border opacity-60',
          )}>

            {/* Tab bar */}
            <div className="flex items-center gap-0.5 border-b border-border/60 bg-muted/60 px-2 py-1.5">
              {(['message', 'request'] as const).map(tabId => (
                <button
                  key={tabId}
                  type="button"
                  onClick={() => setTab(tabId)}
                  disabled={!connected}
                  className={cn(
                    'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                    tab === tabId
                      ? 'bg-background text-foreground shadow ring-1 ring-border/70'
                      : 'text-muted-foreground hover:text-foreground disabled:pointer-events-none',
                  )}
                >
                  {tabId === 'message' ? t('composer.tab_message') : t('composer.tab_request')}
                </button>
              ))}
            </div>

            {/* Message tab */}
            {tab === 'message' && (
              <div className="px-4 pt-3 pb-2">
                <textarea
                  ref={textRef}
                  value={text}
                  onChange={handleTextChange}
                  onKeyDown={handleTextKeyDown}
                  placeholder={connected ? (placeholders[placeholderIdx] ?? placeholders[0]) : t('composer.placeholder_connecting')}
                  disabled={!connected}
                  rows={1}
                  className="w-full resize-none bg-transparent text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none disabled:opacity-50"
                  style={{ minHeight: '1.75rem', maxHeight: '10rem' }}
                />
              </div>
            )}

            {/* Create Request tab */}
            {tab === 'request' && (
              <div className="max-h-[55vh] overflow-y-auto overscroll-contain sm:max-h-[30rem]">
                <div className="space-y-2.5 px-3 pt-3 pb-2.5">
                  {/* Description */}
                  <textarea
                    ref={textRef}
                    value={text}
                    onChange={handleTextChange}
                    onKeyDown={handleTextKeyDown}
                    placeholder={t('composer.describe')}
                    disabled={!connected}
                    rows={2}
                    className="w-full resize-none bg-transparent px-1 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none disabled:opacity-50"
                    style={{ minHeight: '2.5rem', maxHeight: '5rem' }}
                  />
                  {/* Approver */}
                  <div className="rounded-xl border border-border/70 bg-muted/40 px-3 py-2">
                    <label className="mb-1 block text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      {t('composer.approver')}
                    </label>
                    <input
                      value={approver}
                      onChange={e => setApprover(e.target.value)}
                      placeholder={t('composer.approver_placeholder')}
                      className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
                    />
                  </div>
                  {/* Code change */}
                  <div>
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground">{t('composer.code_change')}</span>
                      <LanguagePicker value={language} onChange={setLanguage} />
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
                      <CodeEditor value={before} onChange={setBefore} label="Before" tone="before" language={language} />
                      <CodeEditor value={after}  onChange={setAfter}  label="After"  tone="after"  language={language} />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Footer */}
            <div className={cn(
              'flex items-center justify-end gap-2 px-3 py-2',
              tab === 'request' && 'border-t border-border/50 bg-muted/40',
            )}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="icon-sm" onClick={submit} disabled={!canSend}
                    className="h-7 w-7 rounded-xl" aria-label="Send">
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" align="end">
                  <span className="font-medium">Send</span>
                  <span className="ml-2 opacity-60">↵</span>
                  <span className="ml-3 opacity-40">·</span>
                  <span className="ml-3 opacity-60">⇧↵ newline</span>
                  {tab === 'message' && (
                    <>
                      <span className="ml-3 opacity-40">·</span>
                      <span className="ml-3 opacity-60">/ commands</span>
                    </>
                  )}
                </TooltipContent>
              </Tooltip>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
