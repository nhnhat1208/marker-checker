import type { UiResponse } from '@/lib/chatTypes'

export const CHAT_MESSAGE_ROLE = {
  USER: 'user',
  AGENT: 'agent',
} as const

export const CHAT_UI_RESPONSE_KIND = {
  CONFIRMATION_REQUIRED: 'confirmation_required',
  REQUEST_STATUS: 'request_status',
  REQUEST_LIST: 'request_list',
  REQUEST_SUBMITTED: 'request_submitted',
} as const

export const CHAT_REQUEST_STATUS = {
  SUBMITTED: 'submitted',
  IN_REVIEW: 'in_review',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  CANCELLED: 'cancelled',
  NEEDS_INFO: 'needs_info',
  ERROR: 'error',
} as const

export const CHAT_DRAFT_ACTION = {
  CONFIRM: 'confirm',
  DISCARD: 'discard',
} as const

export const CHAT_REVIEW_ACTION = {
  APPROVE: 'approve',
  REJECT: 'reject',
  NEED_INFO: 'needinfo',
} as const

export const CHAT_PENDING_ACTION_KIND = {
  DRAFT: 'draft',
  REVIEW: 'review',
} as const

export const CHAT_TIMING = {
  STRUCTURED_FALLBACK_MS: 15_000,
  PLAIN_AGENT_DEDUPE_WINDOW_MS: 2_000,
} as const

export const CHAT_COPY = {
  REQUEST_FALLBACK_TITLE: 'Request',
  REQUESTS_TITLE: 'Requests',
  DRAFT_READY_TITLE: 'Draft ready to submit',
  DRAFT_READY_BODY: 'Review the extracted fields, then confirm to route the request.',
  NO_REQUESTS_FOUND: 'No requests found.',
  DRAFT_PENDING: {
    [CHAT_DRAFT_ACTION.CONFIRM]: 'Confirming draft...',
    [CHAT_DRAFT_ACTION.DISCARD]: 'Discarding draft...',
  },
  REVIEW_PENDING: {
    [CHAT_REVIEW_ACTION.APPROVE]: 'Applying approval...',
    [CHAT_REVIEW_ACTION.REJECT]: 'Sending rejection...',
    [CHAT_REVIEW_ACTION.NEED_INFO]: 'Requesting more info...',
  },
} as const

export type ChatMessageRole = typeof CHAT_MESSAGE_ROLE[keyof typeof CHAT_MESSAGE_ROLE]
export type DraftAction = typeof CHAT_DRAFT_ACTION[keyof typeof CHAT_DRAFT_ACTION]
export type ReviewAction = typeof CHAT_REVIEW_ACTION[keyof typeof CHAT_REVIEW_ACTION]
export type ReviewNoteAction =
  | typeof CHAT_REVIEW_ACTION.REJECT
  | typeof CHAT_REVIEW_ACTION.NEED_INFO

export type PendingAction =
  | { kind: typeof CHAT_PENDING_ACTION_KIND.DRAFT; op: DraftAction }
  | { kind: typeof CHAT_PENDING_ACTION_KIND.REVIEW; op: ReviewAction; requestId: string }

export type ChatMessage = {
  role: ChatMessageRole
  text: string
  timestamp: number
  uiResponse?: UiResponse
}
