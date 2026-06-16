import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { UiRequestSummary } from '@/lib/chatTypes'
import {
  CHAT_REVIEW_ACTION,
  type PendingAction,
  type ReviewAction,
  type ReviewNoteAction,
} from '@/lib/chatUi'
import { cn } from '@/lib/utils'
import ChangeSummary from './ChangeSummary'
import CodeBlock from './CodeBlock'
import CodeChangeSection from './CodeChangeSection'
import ImpactNoteSummary from './ImpactNoteSummary'
import {
  canReviewRequest,
  getDefaultStatusConfig,
  getStatusConfig,
  POSITIVE_ACTION_CLASS,
  SOFT_DESTRUCTIVE_ACTION_CLASS,
  WARNING_ACTION_CLASS,
} from './config'

type Props = {
  request: UiRequestSummary
  viewerHandle: string
  actionPending?: boolean
  pendingAction?: PendingAction | null
  onReviewAction?: (action: ReviewAction, requestId: string, note?: string) => void
}

function getRequestTextDisplay(rawText: string) {
  const truncIdx = rawText.search(/\n\n(?:Approver:|Before |After |Current state:|Proposed state:|Before change:|After change:|```)/)
  return {
    text: (truncIdx >= 0 ? rawText.slice(0, truncIdx) : rawText).trim(),
    textHasCodeBlocks: rawText.includes('```') || truncIdx >= 0,
  }
}

export default function RequestCard({
  request,
  viewerHandle,
  actionPending = false,
  pendingAction,
  onReviewAction,
}: Props) {
  const { t } = useTranslation()
  const statusConfig = getStatusConfig(t)
  const cfg = statusConfig[request.review_status] ?? getDefaultStatusConfig(t)
  const Icon = cfg.icon
  const requestFormat = request.structured_payload?.request_format ?? 'text'
  const [noteMode, setNoteMode] = useState<ReviewNoteAction | null>(null)
  const [note, setNote] = useState('')
  const canReview = canReviewRequest(request, viewerHandle)
  const pendingReview = (
    pendingAction?.kind === 'review' && pendingAction.requestId === request.request_id
      ? pendingAction.op
      : null
  )
  const rawText = request.request_text ?? ''
  const { text: requestTextDisplay, textHasCodeBlocks } = getRequestTextDisplay(rawText)

  const submitNoteAction = () => {
    if (!noteMode) return
    const trimmed = note.trim()
    if (!trimmed) return
    onReviewAction?.(noteMode, request.request_id, trimmed)
    setNote('')
    setNoteMode(null)
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-background shadow-md">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-border/70 bg-muted/50 px-4 py-2.5">
        <span className={cn('flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium', cfg.cls)}>
          <Icon className="h-3 w-3" />
          {cfg.label}
        </span>
        <span className="select-all font-mono text-xs text-muted-foreground">{request.request_id}</span>
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
              <span>
                {t('chat_card.meta_requester', 'Requester')}: <span className="font-medium text-foreground">{request.requester_handle}</span>
              </span>
            )}
            {request.approver_handle && (
              <span>
                {t('chat_card.meta_approver', 'Approver')}: <span className="font-medium text-foreground">{request.approver_handle}</span>
              </span>
            )}
            {request.target_label && (
              <span>
                {t('chat_card.meta_target', 'Target')}: <span className="font-mono font-medium text-foreground">{request.target_label}</span>
              </span>
            )}
          </div>
        )}

        <ImpactNoteSummary note={request.impact_note ?? ''} />

        {requestTextDisplay && (
          requestFormat === 'text' ? (
            <div className="space-y-1.5 rounded-lg bg-muted/40 px-3 py-2.5">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70">{t('chat_card.description', 'Description')}</p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{requestTextDisplay}</p>
            </div>
        ) : (
            <CodeBlock content={requestTextDisplay} language={requestFormat} tone="neutral" label={t('chat_card.description', 'Description')} />
          )
        )}

        <CodeChangeSection request={request} />

        {!request.structured_payload && !textHasCodeBlocks && (
          <ChangeSummary
            from={request.change_from_summary}
            to={request.change_to_summary}
            fromLabel={t('change_summary.current', 'Current state')}
            toLabel={t('change_summary.proposed', 'Proposed state')}
          />
        )}

        {canReview && (
          <div className="rounded-lg border border-border/70 bg-muted/30 p-3">
            {pendingReview ? (
              <div className="flex items-center">
                <span className="inline-flex items-center rounded-full border border-border/70 bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
                  {pendingReview === CHAT_REVIEW_ACTION.APPROVE
                    ? t('chat_card.pending.review_approve', 'Applying approval...')
                    : pendingReview === CHAT_REVIEW_ACTION.REJECT
                      ? t('chat_card.pending.review_reject', 'Sending rejection...')
                      : t('chat_card.pending.review_need_info', 'Requesting more info...')}
                </span>
              </div>
            ) : noteMode ? (
              <div className="space-y-2.5">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70">
                  {noteMode === CHAT_REVIEW_ACTION.REJECT
                    ? t('chat_card.reject_reason', 'Reject reason')
                    : t('chat_card.need_info_prompt', 'Need info prompt')}
                </p>
                <Input
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      submitNoteAction()
                    }
                  }}
                  placeholder={
                    noteMode === CHAT_REVIEW_ACTION.REJECT
                      ? t('chat_card.reject_placeholder', 'Explain why this request should be rejected')
                      : t('chat_card.need_info_placeholder', 'Ask for the missing detail you need')
                  }
                  disabled={actionPending}
                  className="h-9 bg-background"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionPending || !note.trim()}
                  className={noteMode === CHAT_REVIEW_ACTION.REJECT ? SOFT_DESTRUCTIVE_ACTION_CLASS : WARNING_ACTION_CLASS}
                  onClick={submitNoteAction}
                >
                    {noteMode === CHAT_REVIEW_ACTION.REJECT
                      ? t('chat_card.send_rejection', 'Send rejection')
                      : t('chat_card.request_info', 'Request info')}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={actionPending}
                    onClick={() => {
                      setNote('')
                      setNoteMode(null)
                    }}
                  >
                    {t('chat_card.cancel', 'Cancel')}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={actionPending}
                  className={POSITIVE_ACTION_CLASS}
                  onClick={() => onReviewAction?.(CHAT_REVIEW_ACTION.APPROVE, request.request_id)}
                >
                  {t('chat_card.approve', 'Approve')}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={actionPending}
                  className={WARNING_ACTION_CLASS}
                  onClick={() => setNoteMode(CHAT_REVIEW_ACTION.NEED_INFO)}
                >
                  {t('chat_card.need_info', 'Need info')}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={actionPending}
                  className={SOFT_DESTRUCTIVE_ACTION_CLASS}
                  onClick={() => setNoteMode(CHAT_REVIEW_ACTION.REJECT)}
                >
                  {t('chat_card.reject', 'Reject')}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
