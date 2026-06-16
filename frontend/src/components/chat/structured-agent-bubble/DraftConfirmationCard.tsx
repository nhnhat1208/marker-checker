import { Button } from '@/components/ui/button'
import { useTranslation } from 'react-i18next'
import type { UiDraftSummary } from '@/lib/chatTypes'
import {
  CHAT_DRAFT_ACTION,
  type DraftAction,
  type PendingAction,
} from '@/lib/chatUi'
import ChangeSummary from './ChangeSummary'
import {
  POSITIVE_ACTION_CLASS,
  SOFT_DESTRUCTIVE_ACTION_CLASS,
} from './config'

type Props = {
  draft: UiDraftSummary
  actionPending?: boolean
  pendingAction?: PendingAction | null
  onDraftAction?: (op: DraftAction) => void
}

export default function DraftConfirmationCard({
  draft,
  actionPending = false,
  pendingAction,
  onDraftAction,
}: Props) {
  const { t } = useTranslation()
  const pendingDraft = pendingAction?.kind === 'draft' ? pendingAction.op : null

  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-background shadow-md">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/70 bg-primary/5 px-4 py-2.5">
        <span className="rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
          {t('chat_card.draft_badge', 'Draft')}
        </span>
        {draft.parser && (
          <span className="rounded-full border border-border bg-background px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            {draft.parser === 'llm_assisted' ? t('chat_card.draft_parser_llm', 'LLM assisted') : draft.parser}
          </span>
        )}
      </div>

      <div className="space-y-3 p-4">
        {(draft.requester_handle || draft.approver_handle || draft.target_label) && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            {draft.requester_handle && (
              <span>
                {t('chat_card.meta_requester', 'Requester')}: <span className="font-medium text-foreground">{draft.requester_handle}</span>
              </span>
            )}
            {draft.approver_handle && (
              <span>
                {t('chat_card.meta_approver', 'Approver')}: <span className="font-medium text-foreground">{draft.approver_handle}</span>
              </span>
            )}
            {draft.target_label && (
              <span>
                {t('chat_card.meta_target', 'Target')}: <span className="font-mono font-medium text-foreground">{draft.target_label}</span>
              </span>
            )}
          </div>
        )}

        <ChangeSummary
          from={draft.change_from_summary}
          to={draft.change_to_summary}
          fromLabel={t('change_summary.current', 'Current state')}
          toLabel={t('change_summary.proposed', 'Proposed state')}
        />

        {pendingDraft ? (
          <div className="pt-1">
            <span className="inline-flex items-center rounded-full border border-border/70 bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground">
              {pendingDraft === CHAT_DRAFT_ACTION.CONFIRM
                ? t('chat_card.pending.draft_confirm', 'Confirming draft...')
                : t('chat_card.pending.draft_discard', 'Discarding draft...')}
            </span>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button
              size="sm"
              variant="outline"
              disabled={actionPending}
              className={POSITIVE_ACTION_CLASS}
              onClick={() => onDraftAction?.(CHAT_DRAFT_ACTION.CONFIRM)}
            >
              {t('chat_card.confirm', 'Confirm')}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={actionPending}
              className={SOFT_DESTRUCTIVE_ACTION_CLASS}
              onClick={() => onDraftAction?.(CHAT_DRAFT_ACTION.DISCARD)}
            >
              {t('chat_card.discard', 'Discard')}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
