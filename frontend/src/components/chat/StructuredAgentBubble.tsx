import { useEffect, useState } from 'react'
import { Highlight, themes } from 'prism-react-renderer'
import { CheckCircle2, XCircle, Clock3, AlertCircle, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/contexts/theme'
import type { UiRequestSummary, UiResponse } from '@/lib/chatTypes'
import CodeDiffPreview from './CodeDiffPreview'

type Props = {
  fallbackText: string
  uiResponse: UiResponse
}

const PAGE_SIZE = 3

/* ── Status config ── */
const STATUS: Record<string, { icon: React.ElementType; label: string; cls: string }> = {
  approved:   { icon: CheckCircle2, label: 'Approved',   cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/50' },
  rejected:   { icon: XCircle,      label: 'Rejected',   cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/50' },
  error:      { icon: XCircle,      label: 'Error',      cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/50' },
  needs_info: { icon: AlertCircle,  label: 'Needs info', cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50' },
}
const STATUS_DEFAULT = { icon: Clock3, label: 'Pending', cls: 'bg-muted/50 text-muted-foreground border-border' }

/* ── Syntax-highlighted code block ── */
function CodeBlock({
  content, language, tone, label,
}: {
  content: string
  language: string
  tone: 'before' | 'after' | 'neutral'
  label: string
}) {
  const { theme } = useTheme()
  const prismTheme = theme === 'dark' ? themes.oneDark : themes.github

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      {/* Tone header */}
      <div className={cn(
        'border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest',
        tone === 'before'
          ? 'border-rose-100 bg-rose-50 text-rose-600 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-400'
          : tone === 'after'
            ? 'border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-400'
            : 'border-border bg-muted/50 text-muted-foreground',
      )}>
        {label}
        <span className="ml-2 font-normal normal-case tracking-normal opacity-60">{language}</span>
      </div>

      <Highlight theme={prismTheme} code={content.replace(/\n$/, '')} language={language}>
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre style={{ ...style, margin: 0, padding: '12px 16px', fontSize: '12px', lineHeight: '1.6', overflow: 'auto', borderRadius: 0 }}>
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  )
}

/* ── View tab toggle ── */
function ViewTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={cn(
      'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
      active
        ? 'bg-foreground text-background shadow-sm'
        : 'text-muted-foreground hover:text-foreground hover:bg-muted',
    )}>
      {children}
    </button>
  )
}

/* ── Code change section ── */
function CodeChangeSection({ request }: { request: UiRequestSummary }) {
  const [view, setView] = useState<'blocks' | 'diff'>('blocks')
  const s = request.structured_payload
  if (!s) return null

  const hasBefore = Boolean(s.before?.enabled && s.before.value.trim())
  const hasAfter  = Boolean(s.after?.enabled  && s.after.value.trim())
  if (!hasBefore && !hasAfter) return null

  const canDiff = hasBefore && hasAfter

  return (
    <div className="space-y-2">
      {canDiff && (
        <div className="flex items-center gap-1">
          <ViewTab active={view === 'blocks'} onClick={() => setView('blocks')}>Side by side</ViewTab>
          <ViewTab active={view === 'diff'}   onClick={() => setView('diff')}>Diff</ViewTab>
        </div>
      )}

      {view === 'blocks' ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {hasBefore && <CodeBlock content={s.before.value} language={s.before.format} tone="before" label="Before" />}
          {hasAfter  && <CodeBlock content={s.after.value}  language={s.after.format}  tone="after" label="After" />}
        </div>
      ) : (
        <CodeDiffPreview
          beforeContent={s.before.value}
          afterContent={s.after.value}
          beforeLabel={s.mode === 'object_change' ? 'From' : 'Before'}
          afterLabel={s.mode === 'object_change' ? 'To'   : 'After'}
          format={s.before.format}
        />
      )}
    </div>
  )
}

/* ── Change summary pills ── */
function ChangeSummary({ from, to }: { from?: string; to?: string }) {
  if (!from && !to) return null
  return (
    <div className="grid gap-2 sm:grid-cols-2 text-xs">
      {from && (
        <div className="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-400">
          <span className="font-medium">From: </span>{from}
        </div>
      )}
      {to && (
        <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-400">
          <span className="font-medium">To: </span>{to}
        </div>
      )}
    </div>
  )
}

/* ── Request card ── */
function RequestCard({ request }: { request: UiRequestSummary }) {
  const cfg = STATUS[request.review_status] ?? STATUS_DEFAULT
  const Icon = cfg.icon
  const requestFormat = request.structured_payload?.request_format ?? 'text'

  // Strip everything from the first structured-preview label onward (LLM fallback artifact).
  // formatStructuredPreview joins parts with \n\n, so labels always appear after a blank line.
  const rawText = request.request_text ?? ''
  const truncIdx = rawText.search(/\n\n(?:Approver:|Before |After |From |To |```)/)
  const requestTextDisplay = (truncIdx >= 0 ? rawText.slice(0, truncIdx) : rawText).trim()

  // Hide from/to pills when structured-preview content leaked into request_text
  const textHasCodeBlocks = rawText.includes('```') || truncIdx >= 0

  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-background shadow-md">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-border/70 bg-muted/50 px-4 py-2.5">
        <span className={cn('flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium', cfg.cls)}>
          <Icon className="h-3 w-3" />
          {cfg.label}
        </span>
        <span className="font-mono text-xs text-muted-foreground select-all">{request.request_id}</span>
        {request.approver_handle && (
          <span className="flex items-center gap-1 text-xs">
            <ChevronRight className="h-3 w-3 text-muted-foreground/50" />
            <span className="font-medium text-foreground">{request.approver_handle}</span>
          </span>
        )}
      </div>

      <div className="space-y-3 p-4">
        {(request.requester_handle || request.approver_handle || request.target_label) && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            {request.requester_handle && (
              <span>Requester: <span className="font-medium text-foreground">{request.requester_handle}</span></span>
            )}
            {request.approver_handle && (
              <span>Approver: <span className="font-medium text-foreground">{request.approver_handle}</span></span>
            )}
            {request.target_label && (
              <span>Target: <span className="font-mono font-medium text-foreground">{request.target_label}</span></span>
            )}
          </div>
        )}
        {requestTextDisplay && (
          requestFormat === 'text' ? (
            <div className="space-y-1.5 rounded-lg bg-muted/40 px-3 py-2.5">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70">Description</p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{requestTextDisplay}</p>
            </div>
          ) : (
            <CodeBlock content={requestTextDisplay} language={requestFormat} tone="neutral" label="Description" />
          )
        )}
        <CodeChangeSection request={request} />
        {!request.structured_payload && !textHasCodeBlocks && (
          <ChangeSummary from={request.change_from_summary} to={request.change_to_summary} />
        )}
      </div>
    </div>
  )
}

function AgentAvatar() {
  return (
    <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary shadow-sm">
      <span className="select-none text-xs font-bold text-primary-foreground">M</span>
    </div>
  )
}

/* ── Top-level bubble ── */
export default function StructuredAgentBubble({ fallbackText, uiResponse }: Props) {
  const requests = uiResponse.requests ?? (uiResponse.request ? [uiResponse.request] : [])
  const hasContent = uiResponse.title || uiResponse.body || requests.length > 0

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  useEffect(() => { setPage(0) }, [search])

  const query = search.toLowerCase().trim()
  const filtered = query
    ? requests.filter(r =>
        [r.request_id, r.target_label, r.approver_handle, r.requester_handle]
          .some(f => f.toLowerCase().includes(query))
      )
    : requests

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const showListControls = requests.length > 1

  if (!hasContent) {
    return (
      <div className="flex items-start gap-2.5">
        <AgentAvatar />
        <div className="max-w-[min(100%,56rem)] rounded-2xl rounded-tl-sm border border-border/80 bg-background px-4 py-3 text-sm leading-7 text-foreground shadow-lg">
          {fallbackText}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2.5">
      <AgentAvatar />
      <div className="max-w-[min(100%,56rem)] rounded-2xl rounded-tl-sm border border-border/80 bg-background px-4 py-3 shadow-lg">
        <div className="space-y-3">
          {uiResponse.title && <p className="text-sm font-semibold text-foreground">{uiResponse.title}</p>}
          {uiResponse.body  && <p className="text-sm leading-7 text-muted-foreground">{uiResponse.body}</p>}

          {showListControls && (
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search requests…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full rounded-lg border border-border/80 bg-background py-1.5 pl-8 pr-3 text-sm outline-none placeholder:text-muted-foreground/50 transition-colors focus:border-primary/60 focus:ring-2 focus:ring-primary/10"
              />
            </div>
          )}

          {paged.map(r => <RequestCard key={r.request_id} request={r} />)}

          {showListControls && filtered.length === 0 && (
            <p className="py-2 text-center text-sm text-muted-foreground">No results for "{search}"</p>
          )}

          {showListControls && totalPages > 1 && (
            <div className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
              <span>
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => p - 1)}
                  disabled={page === 0}
                  className="rounded-md p-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="px-1">{page + 1} / {totalPages}</span>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages - 1}
                  className="rounded-md p-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-30"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
