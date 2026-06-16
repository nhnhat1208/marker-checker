import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import type { UiResponse } from '@/lib/chatTypes'
import { formatChatTimestamp } from '@/lib/chatTime'
import { CHAT_UI_RESPONSE_KIND } from '@/lib/chatUi'
import type { DraftAction, PendingAction, ReviewAction } from '@/lib/chatUi'
import AgentAvatar from './structured-agent-bubble/AgentAvatar'
import DraftConfirmationCard from './structured-agent-bubble/DraftConfirmationCard'
import MissingFieldsCallout from './structured-agent-bubble/MissingFieldsCallout'
import { PAGE_SIZE } from './structured-agent-bubble/config'
import RequestCard from './structured-agent-bubble/RequestCard'

type Props = {
  fallbackText: string
  uiResponse: UiResponse
  timestamp: number
  viewerHandle: string
  missingInfoActionHidden?: boolean
  actionPending?: boolean
  pendingAction?: PendingAction | null
  onDraftAction?: (op: DraftAction) => void
  onReviewAction?: (action: ReviewAction, requestId: string, note?: string) => void
  onMissingFieldClick?: (text: string) => void
}

function filterRequests(query: string, uiResponse: UiResponse) {
  const requests = uiResponse.requests ?? (uiResponse.request ? [uiResponse.request] : [])
  const normalizedQuery = query.toLowerCase().trim()

  if (!normalizedQuery) return requests

  return requests.filter((request) =>
    [request.request_id, request.target_label, request.approver_handle, request.requester_handle]
      .some((field) => field.toLowerCase().includes(normalizedQuery))
  )
}

export default function StructuredAgentBubble({
  fallbackText,
  uiResponse,
  timestamp,
  viewerHandle,
  missingInfoActionHidden = false,
  actionPending = false,
  pendingAction,
  onDraftAction,
  onReviewAction,
  onMissingFieldClick,
}: Props) {
  const { t } = useTranslation()
  const draft = uiResponse.draft ?? null
  const requests = uiResponse.requests ?? (uiResponse.request ? [uiResponse.request] : [])
  const isMissingInfo = uiResponse.status === 'missing_fields' || (uiResponse.missing_fields?.length ?? 0) > 0
  const hasContent = uiResponse.title || uiResponse.body || requests.length > 0 || Boolean(draft)

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  useEffect(() => {
    setPage(0)
  }, [search])

  const filtered = filterRequests(search, uiResponse)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const showListControls = requests.length > 1
  const timeLabel = formatChatTimestamp(timestamp)
  const title = uiResponse.kind === CHAT_UI_RESPONSE_KIND.CONFIRMATION_REQUIRED
    ? t('chat_card.draft_ready_title', 'Draft ready to submit')
    : isMissingInfo
      ? t('missing_info.title', 'Need more info')
      : uiResponse.title
  const body = uiResponse.kind === CHAT_UI_RESPONSE_KIND.CONFIRMATION_REQUIRED
    ? t('chat_card.draft_ready_body', 'Review the extracted fields, then confirm to route the request.')
    : uiResponse.body

  if (!hasContent) {
    return (
      <div className="flex flex-col items-start">
        <div className="flex items-start gap-2.5">
          <AgentAvatar />
          <div className="max-w-[min(100%,56rem)] rounded-2xl rounded-tl-sm border border-border/80 bg-background px-4 py-3 text-sm leading-7 text-foreground shadow-lg">
            {fallbackText}
          </div>
        </div>
        <span className="mt-1 px-1 pl-9 text-left text-[11px] text-muted-foreground/70">
          {timeLabel}
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start">
      <div className="flex items-start gap-2.5">
        <AgentAvatar />
        <div className="max-w-[min(100%,56rem)] rounded-2xl rounded-tl-sm border border-border/80 bg-background px-4 py-3 shadow-lg">
          <div className="space-y-3">
          {title && (
            <p className="text-sm font-semibold text-foreground">
              {title}
            </p>
          )}
          {!isMissingInfo && body && (
            <p className="text-sm leading-7 text-muted-foreground">{body}</p>
          )}
          {isMissingInfo && (
            <MissingFieldsCallout
              missingFields={uiResponse.missing_fields}
              draft={draft}
              onFieldClick={onMissingFieldClick}
              hiddenAction={missingInfoActionHidden}
            />
          )}

          {draft && !isMissingInfo && (
            <DraftConfirmationCard
              draft={draft}
              actionPending={actionPending}
              pendingAction={pendingAction}
              onDraftAction={onDraftAction}
            />
          )}

          {showListControls && (
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="text"
                placeholder={t('chat_card.search_requests', 'Search requests…')}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="h-9 rounded-lg border-border/80 py-1.5 pl-8 pr-3 shadow-none focus-visible:ring-2 focus-visible:ring-primary/10"
              />
            </div>
          )}

          {paged.map((request) => (
            <RequestCard
              key={request.request_id}
              request={request}
              viewerHandle={viewerHandle}
              actionPending={actionPending}
              pendingAction={pendingAction}
              onReviewAction={onReviewAction}
            />
          ))}

          {showListControls && filtered.length === 0 && (
            <p className="py-2 text-center text-sm text-muted-foreground">
              {t('chat_card.no_results', 'No results for "{{query}}"', { query: search })}
            </p>
          )}

          {showListControls && totalPages > 1 && (
            <div className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
              <span>
                {t('chat_card.range_info', '{{start}}–{{end}} of {{total}}', {
                  start: page * PAGE_SIZE + 1,
                  end: Math.min((page + 1) * PAGE_SIZE, filtered.length),
                  total: filtered.length,
                })}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((previous) => previous - 1)}
                  disabled={page === 0}
                  className="rounded-md p-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="px-1">
                  {t('chat_card.page_info', '{{current}} / {{total}}', {
                    current: page + 1,
                    total: totalPages,
                  })}
                </span>
                <button
                  onClick={() => setPage((previous) => previous + 1)}
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
      <span className="mt-1 px-1 pl-9 text-left text-[11px] text-muted-foreground/70">
        {timeLabel}
      </span>
    </div>
  )
}
