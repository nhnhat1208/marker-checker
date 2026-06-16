import type { TFunction } from 'i18next'
import type { ElementType } from 'react'
import { AlertCircle, CheckCircle2, Clock3, XCircle } from 'lucide-react'
import type { UiRequestSummary } from '@/lib/chatTypes'
import { CHAT_REQUEST_STATUS, isPendingReviewStatus } from '@/lib/chatUi'

export const PAGE_SIZE = 3

export const POSITIVE_ACTION_CLASS = [
  '!border-emerald-200',
  '!bg-emerald-500',
  '!text-white',
  'shadow-sm',
  'hover:!bg-emerald-600',
  'hover:!text-white',
  'dark:!border-emerald-800/50',
  'dark:!bg-emerald-500',
  'dark:!text-emerald-950',
  'dark:hover:!bg-emerald-400',
  'dark:hover:!text-emerald-950',
].join(' ')
export const WARNING_ACTION_CLASS = 'border-amber-200 bg-amber-50 text-amber-800 shadow-sm hover:bg-amber-100 hover:text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/20 dark:text-amber-300 dark:hover:bg-amber-950/35'
export const SOFT_DESTRUCTIVE_ACTION_CLASS = 'border-rose-200 bg-rose-50 text-rose-700 shadow-sm hover:bg-rose-100 hover:text-rose-800 dark:border-rose-800/60 dark:bg-rose-950/20 dark:text-rose-300 dark:hover:bg-rose-950/35'

export function getStatusConfig(t: TFunction): Record<string, { icon: ElementType; label: string; cls: string }> {
  return {
    [CHAT_REQUEST_STATUS.SUBMITTED]: { icon: Clock3, label: t('chat_card.status.pending', 'Pending'), cls: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/40 dark:text-slate-300 dark:border-slate-700/50' },
    [CHAT_REQUEST_STATUS.IN_REVIEW]: { icon: Clock3, label: t('chat_card.status.in_review', 'In review'), cls: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800/50' },
    [CHAT_REQUEST_STATUS.APPROVED]: { icon: CheckCircle2, label: t('chat_card.status.approved', 'Approved'), cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/50' },
    [CHAT_REQUEST_STATUS.REJECTED]: { icon: XCircle, label: t('chat_card.status.rejected', 'Rejected'), cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/50' },
    [CHAT_REQUEST_STATUS.CANCELLED]: { icon: XCircle, label: t('chat_card.status.cancelled', 'Cancelled'), cls: 'bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-900/40 dark:text-zinc-300 dark:border-zinc-700/50' },
    [CHAT_REQUEST_STATUS.ERROR]: { icon: XCircle, label: t('chat_card.status.error', 'Error'), cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/50' },
    [CHAT_REQUEST_STATUS.NEEDS_INFO]: { icon: AlertCircle, label: t('chat_card.status.needs_info', 'Needs info'), cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50' },
  }
}

export function getDefaultStatusConfig(t: TFunction) {
  return {
    icon: Clock3,
    label: t('chat_card.status.pending', 'Pending'),
    cls: 'bg-muted/50 text-muted-foreground border-border',
  }
}

export function canReviewRequest(request: UiRequestSummary, viewerHandle: string) {
  return (
    isPendingReviewStatus(request.review_status)
    && request.approver_handle.trim().toLowerCase() === viewerHandle.trim().toLowerCase()
  )
}
