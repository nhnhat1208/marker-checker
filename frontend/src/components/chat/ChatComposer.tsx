import { useEffect, useRef, useState } from 'react'
import { Send, Paperclip, PencilLine, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { CodeFormat, StructuredRequestPayload } from '@/lib/chatTypes'
import {
  CHAT_COMPOSER_STORAGE_KEY,
  CHAT_COMPOSER_TAB,
  COMPOSER_SHORTCUT_HINTS,
  EDITOR_LANGUAGE,
  type EditorLanguage,
  type ComposerTab,
  SLASH_COMMAND_CATEGORY_ORDER,
  SLASH_COMMANDS,
  type SlashCommand,
} from '@/lib/chatComposerConfig'
import { cn } from '@/lib/utils'
import CodeChangesDialog from './CodeChangesDialog'

function toCodeFormat(lang: EditorLanguage): CodeFormat {
  if (lang === EDITOR_LANGUAGE.YAML) return 'yaml'
  if (lang === EDITOR_LANGUAGE.JSON) return 'json'
  return 'text'
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
  const filtered = SLASH_COMMANDS.filter(command => command.cmd.slice(1).startsWith(query.toLowerCase()))

  useEffect(() => { activeRef.current?.scrollIntoView({ block: 'nearest' }) }, [activeIdx])

  if (!filtered.length) return null

  const grouped = SLASH_COMMAND_CATEGORY_ORDER.reduce<Record<string, SlashCommand[]>>((acc, category) => {
    const items = filtered.filter(command => command.category === category)
    if (items.length) acc[category] = items
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
        {COMPOSER_SHORTCUT_HINTS.map(([key, hint]) => (
          <span key={key} className="text-[10px] text-muted-foreground/60">
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{key}</kbd>{' '}{hint}
          </span>
        ))}
      </div>
    </div>
  )
}

type Props = {
  connected: boolean
  onSend: (payload: string | StructuredRequestPayload) => void
  fillText?: string
  onFillConsumed?: () => void
}

export default function ChatComposer({ connected, onSend, fillText, onFillConsumed }: Props) {
  const { t } = useTranslation()
  const placeholders = t('composer.placeholders', { returnObjects: true }) as string[]
  const [tab, setTab]               = useState<ComposerTab>(CHAT_COMPOSER_TAB.MESSAGE)
  const [text, setText]             = useState('')
  const [approver, setApprover]     = useState('')
  const [before, setBefore]         = useState('')
  const [after, setAfter]           = useState('')
  const [language, setLanguage]     = useState<EditorLanguage>(EDITOR_LANGUAGE.YAML)
  const [showCodeDialog, setShowCodeDialog] = useState(false)
  const [placeholderIdx, setPlaceholderIdx] = useState(0)
  const [pickerIdx, setPickerIdx]   = useState(0)
  const textRef = useRef<HTMLTextAreaElement>(null)

  // Slash command picker (message tab only)
  const slashMatch   = tab === CHAT_COMPOSER_TAB.MESSAGE ? text.match(/^\/(\S*)$/) : null
  const showPicker   = Boolean(slashMatch && connected)
  const pickerQuery  = slashMatch ? slashMatch[1] : ''
  const filteredCmds = SLASH_COMMANDS.filter(command => command.cmd.slice(1).startsWith(pickerQuery.toLowerCase()))

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
      const stored = window.localStorage.getItem(CHAT_COMPOSER_STORAGE_KEY)
      if (!stored) return
      const p = JSON.parse(stored) as Partial<{
        tab: ComposerTab; text: string; approver: string; before: string; after: string; language: EditorLanguage
      }>
      if (p.tab === CHAT_COMPOSER_TAB.MESSAGE || p.tab === CHAT_COMPOSER_TAB.REQUEST) setTab(p.tab)
      setText(typeof p.text === 'string' ? p.text : '')
      setApprover(typeof p.approver === 'string' ? p.approver : '')
      setBefore(typeof p.before === 'string' ? p.before : '')
      setAfter(typeof p.after === 'string' ? p.after : '')
      if (p.language) setLanguage(p.language)
    } catch { window.localStorage.removeItem(CHAT_COMPOSER_STORAGE_KEY) }
  }, [])

  // Consume external fill text (from empty-state examples)
  useEffect(() => {
    if (!fillText) return
    setText(fillText)
    setTab(CHAT_COMPOSER_TAB.MESSAGE)
    setShowCodeDialog(false)
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
    if (!text && !approver && !before && !after) {
      window.localStorage.removeItem(CHAT_COMPOSER_STORAGE_KEY)
      return
    }
    window.localStorage.setItem(
      CHAT_COMPOSER_STORAGE_KEY,
      JSON.stringify({ tab, text, approver, before, after, language }),
    )
  }, [after, approver, before, language, tab, text])

  const canSend = connected && (
    tab === CHAT_COMPOSER_TAB.MESSAGE
      ? Boolean(text.trim())
      : Boolean(text.trim() || before.trim() || after.trim())
  )
  const hasCodeChanges = Boolean(before.trim() || after.trim())

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
    if (tab === CHAT_COMPOSER_TAB.MESSAGE) {
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
    setShowCodeDialog(false)
    window.localStorage?.removeItem(CHAT_COMPOSER_STORAGE_KEY)
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
            <div className="flex items-center gap-0.5 border-b border-border/60 bg-muted/40 px-2 py-1.5">
              {([CHAT_COMPOSER_TAB.MESSAGE, CHAT_COMPOSER_TAB.REQUEST] as const).map(tabId => (
                <button
                  key={tabId}
                  type="button"
                  onClick={() => setTab(tabId)}
                  disabled={!connected}
                  className={cn(
                    'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                    tab === tabId
                      ? 'bg-background text-foreground shadow ring-1 ring-border/70'
                      : 'text-muted-foreground hover:text-foreground disabled:pointer-events-none',
                  )}
                >
                  {tabId === CHAT_COMPOSER_TAB.MESSAGE ? t('composer.tab_message') : t('composer.tab_request')}
                </button>
              ))}
            </div>

            {/* Message tab */}
            {tab === CHAT_COMPOSER_TAB.MESSAGE && (
              <div className="px-4 pt-3 pb-2">
                <Textarea
                  ref={textRef}
                  value={text}
                  onChange={handleTextChange}
                  onKeyDown={handleTextKeyDown}
                  placeholder={connected ? (placeholders[placeholderIdx] ?? placeholders[0]) : t('composer.placeholder_connecting')}
                  disabled={!connected}
                  rows={1}
                  className="min-h-0 resize-none border-0 bg-transparent px-0 py-0 text-sm leading-relaxed shadow-none focus-visible:ring-0 disabled:opacity-50"
                  style={{ minHeight: '1.75rem', maxHeight: '10rem' }}
                />
              </div>
            )}

            {/* Create Request tab */}
            {tab === CHAT_COMPOSER_TAB.REQUEST && (
              <div className="space-y-3 px-4 py-3 sm:px-5">
                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Request</p>
                  <Textarea
                    ref={textRef}
                    value={text}
                    onChange={handleTextChange}
                    onKeyDown={handleTextKeyDown}
                    placeholder={t('composer.describe')}
                    disabled={!connected}
                    rows={2}
                    className="min-h-0 resize-none rounded-xl border-border/70 bg-background px-3 py-2.5 text-sm leading-relaxed shadow-none focus-visible:ring-2 focus-visible:ring-primary/10 disabled:opacity-50"
                    style={{ minHeight: '3.25rem', maxHeight: '4.75rem' }}
                  />
                </div>

                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Approver email</p>
                  <Input
                    value={approver}
                    onChange={e => setApprover(e.target.value)}
                    placeholder={t('composer.approver_placeholder')}
                    className="h-9 rounded-xl border-border/70 bg-background px-3 text-sm shadow-none focus-visible:ring-2 focus-visible:ring-primary/10"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant={hasCodeChanges ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setShowCodeDialog(true)}
                    className={cn(
                      'rounded-full',
                      hasCodeChanges
                        ? 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90'
                        : 'border-border/70 bg-background text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <Paperclip className="h-3.5 w-3.5" />
                    {hasCodeChanges ? 'Code attached' : 'Attach code changes'}
                  </Button>

                  {hasCodeChanges && (
                    <>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowCodeDialog(true)}
                        className="rounded-full text-muted-foreground hover:text-foreground"
                      >
                        <PencilLine className="h-3.5 w-3.5" />
                        Edit
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setBefore('')
                          setAfter('')
                          setShowCodeDialog(false)
                        }}
                        className="rounded-full text-muted-foreground hover:text-foreground"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Remove
                      </Button>
                    </>
                  )}
                </div>

                {!hasCodeChanges && (
                  <p className="text-[11px] text-muted-foreground/70">
                    Optional. Add code only when the diff matters.
                  </p>
                )}
              </div>
            )}

            {/* Footer */}
            <div className={cn(
              'flex items-center justify-end gap-2 px-3 py-2',
              tab === CHAT_COMPOSER_TAB.REQUEST && 'border-t border-border/50 bg-muted/40',
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
                  {tab === CHAT_COMPOSER_TAB.MESSAGE && (
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
      <CodeChangesDialog
        open={showCodeDialog}
        onOpenChange={setShowCodeDialog}
        before={before}
        after={after}
        language={language}
        onSave={({ before: nextBefore, after: nextAfter, language: nextLanguage }) => {
          setBefore(nextBefore)
          setAfter(nextAfter)
          setLanguage(nextLanguage)
        }}
        onClear={() => {
          setBefore('')
          setAfter('')
        }}
      />
    </div>
  )
}
