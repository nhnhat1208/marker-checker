import { cn } from '@/lib/utils'
import { computeLineDiff, getChangedEntries, summarizeDiff } from '@/lib/codeDiff'

type Props = {
  afterContent: string
  afterLabel: string
  beforeContent: string
  beforeLabel: string
  className?: string
  format: string
  showRawToggle?: boolean
}

function RawCodeBlock({ content, label, tone }: { content: string; label: string; tone: 'before' | 'after' }) {
  return (
    <div className={cn(
      'overflow-hidden rounded-xl border',
      'bg-[#f6f8fa] border-slate-200',
      'dark:bg-[#0d1117] dark:border-[#30363d]',
    )}>
      <div className={cn(
        'border-b px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em]',
        tone === 'before'
          ? 'border-rose-100 bg-rose-50 text-rose-600 dark:border-[#3d0000]/60 dark:bg-[#3d0000]/30 dark:text-[#ff7b72]'
          : 'border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-[#003820]/60 dark:bg-[#003820]/40 dark:text-[#56d364]',
      )}>
        {label}
      </div>
      <pre className={cn(
        'overflow-x-auto px-4 py-3 text-[12px] leading-6',
        'text-[#24292f]',
        'dark:text-[#e6edf3]',
      )}>
        <code>{content}</code>
      </pre>
    </div>
  )
}

export default function CodeDiffPreview({
  afterContent, afterLabel, beforeContent, beforeLabel, className, format, showRawToggle = false,
}: Props) {
  const entries = computeLineDiff(beforeContent, afterContent)
  const stats   = summarizeDiff(entries)
  const preview = getChangedEntries(entries, 8)
  const hasChanges = stats.added > 0 || stats.removed > 0

  return (
    <div className={cn(
      'overflow-hidden rounded-xl border',
      'bg-white border-slate-200',
      'dark:bg-[#0d1117] dark:border-[#30363d]',
      className,
    )}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/50 px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Diff preview
          </span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {format}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] font-medium">
          <span className={cn('rounded-full px-2 py-0.5', 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300')}>
            +{stats.added}
          </span>
          <span className={cn('rounded-full px-2 py-0.5', 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300')}>
            -{stats.removed}
          </span>
        </div>
      </div>

      {!hasChanges ? (
        <div className="px-4 py-4 text-sm text-muted-foreground">No line-level diff detected.</div>
      ) : (
        <div className="px-3 py-3">
          <div className={cn(
            'overflow-hidden rounded-lg border',
            'border-border/50 bg-muted/20',
            'dark:bg-[#0d1117] dark:border-[#30363d]/60',
          )}>
            {preview.entries.map((entry, index) => (
              <div key={`${entry.type}-${index}-${entry.line}`}
                className={cn(
                  'flex items-start gap-3 px-3 py-1.5 font-mono text-[12px] leading-6',
                  entry.type === 'added'
                    ? 'bg-emerald-50 text-emerald-900 dark:bg-emerald-500/10 dark:text-emerald-100'
                    : 'bg-rose-50 text-rose-900 dark:bg-rose-500/10 dark:text-rose-100',
                )}>
                <span className="mt-[1px] w-4 shrink-0 text-center text-[11px] font-bold">
                  {entry.type === 'added' ? '+' : '-'}
                </span>
                <span className="min-w-0 whitespace-pre-wrap break-all">{entry.line || ' '}</span>
              </div>
            ))}
          </div>
          {preview.hiddenCount > 0 && (
            <div className="mt-2 text-xs text-muted-foreground">
              {preview.hiddenCount} more changed lines hidden
            </div>
          )}
        </div>
      )}

      {showRawToggle && (
        <details className="border-t border-border">
          <summary className={cn(
            'cursor-pointer list-none px-4 py-2.5 text-xs font-medium transition-colors',
            'text-muted-foreground hover:text-foreground',
          )}>
            Show raw blocks
          </summary>
          <div className="grid gap-3 px-3 pb-3 sm:grid-cols-2">
            <RawCodeBlock content={beforeContent} label={beforeLabel} tone="before" />
            <RawCodeBlock content={afterContent}  label={afterLabel}  tone="after"  />
          </div>
        </details>
      )}
    </div>
  )
}
