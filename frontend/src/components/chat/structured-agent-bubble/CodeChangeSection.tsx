import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { UiRequestSummary } from '@/lib/chatTypes'
import { cn } from '@/lib/utils'
import CodeDiffPreview from '../CodeDiffPreview'
import CodeBlock from './CodeBlock'

function ViewTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
        active
          ? 'bg-foreground text-background shadow-sm'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

type Props = {
  request: UiRequestSummary
}

export default function CodeChangeSection({ request }: Props) {
  const { t } = useTranslation()
  const [view, setView] = useState<'blocks' | 'diff'>('blocks')
  const structuredPayload = request.structured_payload
  if (!structuredPayload) return null

  const hasBefore = Boolean(structuredPayload.before?.enabled && structuredPayload.before.value.trim())
  const hasAfter = Boolean(structuredPayload.after?.enabled && structuredPayload.after.value.trim())
  if (!hasBefore && !hasAfter) return null

  const canDiff = hasBefore && hasAfter

  return (
    <div className="space-y-2">
      {canDiff && (
        <div className="flex items-center gap-1">
          <ViewTab active={view === 'blocks'} onClick={() => setView('blocks')}>
            Side by side
          </ViewTab>
          <ViewTab active={view === 'diff'} onClick={() => setView('diff')}>
            Diff
          </ViewTab>
        </div>
      )}

      {view === 'blocks' ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {hasBefore && (
            <CodeBlock
              content={structuredPayload.before.value}
              language={structuredPayload.before.format}
              tone="before"
              label="Before"
            />
          )}
          {hasAfter && (
            <CodeBlock
              content={structuredPayload.after.value}
              language={structuredPayload.after.format}
              tone="after"
              label="After"
            />
          )}
        </div>
      ) : (
        <CodeDiffPreview
          beforeContent={structuredPayload.before.value}
          afterContent={structuredPayload.after.value}
          beforeLabel={
            structuredPayload.mode === 'object_change'
              ? t('code_change.before_state', 'Before change')
              : t('code_change.before_block', 'Before')
          }
          afterLabel={
            structuredPayload.mode === 'object_change'
              ? t('code_change.after_state', 'After change')
              : t('code_change.after_block', 'After')
          }
          format={structuredPayload.before.format}
        />
      )}
    </div>
  )
}
