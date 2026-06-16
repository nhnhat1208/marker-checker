import type {
  StructuredRequestPayload,
  UiDraftSummary,
  UiRequestSummary,
  UiResponse,
} from '@/lib/chatTypes'
import {
  CHAT_COPY,
  CHAT_REQUEST_STATUS,
  CHAT_UI_RESPONSE_KIND,
} from './constants'

function asUiRequestSummary(request: Record<string, unknown>): UiRequestSummary {
  return {
    request_id: typeof request.request_id === 'string' ? request.request_id : CHAT_COPY.REQUEST_FALLBACK_TITLE,
    requester_handle: typeof request.requester_handle === 'string' ? request.requester_handle : '',
    approver_handle: typeof request.approver_handle === 'string' ? request.approver_handle : '',
    target_label: typeof request.target_label === 'string' ? request.target_label : '',
    change_from_summary: typeof request.change_from_summary === 'string' ? request.change_from_summary : '',
    change_to_summary: typeof request.change_to_summary === 'string' ? request.change_to_summary : '',
    review_status: typeof request.review_status === 'string' ? request.review_status : 'ok',
    request_text: typeof request.request_text === 'string' ? request.request_text : '',
    structured_payload:
      request.structured_payload && typeof request.structured_payload === 'object'
        ? request.structured_payload as StructuredRequestPayload
        : null,
    impact_note: typeof request.impact_note === 'string' ? request.impact_note : null,
  }
}

function asUiDraftSummary(draft: Record<string, unknown>): UiDraftSummary {
  return {
    requester_handle: typeof draft.requester_handle === 'string' ? draft.requester_handle : '',
    approver_handle: typeof draft.approver_handle === 'string' ? draft.approver_handle : '',
    target_label: typeof draft.target_label === 'string' ? draft.target_label : '',
    change_from_summary: typeof draft.change_from_summary === 'string' ? draft.change_from_summary : '',
    change_to_summary: typeof draft.change_to_summary === 'string' ? draft.change_to_summary : '',
    parser: typeof draft.parser === 'string' ? draft.parser : '',
  }
}

export function deriveUiResponse(
  response: Record<string, unknown>,
  incoming?: UiResponse,
): UiResponse | undefined {
  if (incoming) return incoming

  const rawMissingFields = response['missing_fields']
  const missingFields = Array.isArray(rawMissingFields)
    ? rawMissingFields.filter((item): item is string => typeof item === 'string' && item.trim())
    : []
  if (response.status === 'missing_fields' || missingFields.length > 0) {
    const message =
      typeof response.message === 'string' && response.message.trim()
        ? response.message.trim()
        : typeof response.summary_message === 'string' && response.summary_message.trim()
          ? response.summary_message.trim()
          : undefined
    return {
      kind: 'missing_fields',
      title: 'Need more info',
      body: message,
      status: 'missing_fields',
      missing_fields: missingFields.length > 0 ? missingFields : undefined,
      guidance_message: message,
      draft:
        response.draft && typeof response.draft === 'object'
          ? asUiDraftSummary(response.draft as Record<string, unknown>)
          : undefined,
    }
  }

  if (
    response.status === CHAT_UI_RESPONSE_KIND.CONFIRMATION_REQUIRED
    && response.draft
    && typeof response.draft === 'object'
  ) {
    return {
      kind: CHAT_UI_RESPONSE_KIND.CONFIRMATION_REQUIRED,
      title: CHAT_COPY.DRAFT_READY_TITLE,
      body: CHAT_COPY.DRAFT_READY_BODY,
      status: CHAT_UI_RESPONSE_KIND.CONFIRMATION_REQUIRED,
      draft: asUiDraftSummary(response.draft as Record<string, unknown>),
    }
  }

  if (response.request && typeof response.request === 'object') {
    return {
      kind: CHAT_UI_RESPONSE_KIND.REQUEST_STATUS,
      title: `Request ${typeof response.request.request_id === 'string' ? response.request.request_id : ''}`.trim(),
      body:
        typeof response.summary_message === 'string'
          ? response.summary_message
          : typeof response.message === 'string'
            ? response.message
            : undefined,
      status: typeof response.request.review_status === 'string' ? response.request.review_status : undefined,
      request: asUiRequestSummary(response.request as Record<string, unknown>),
    }
  }

  if (Array.isArray(response.requests)) {
    return {
      kind: CHAT_UI_RESPONSE_KIND.REQUEST_LIST,
      title: typeof response.message === 'string' ? response.message.split('\n')[0] : CHAT_COPY.REQUESTS_TITLE,
      body: typeof response.summary_message === 'string' ? response.summary_message : undefined,
      status: typeof response.status === 'string' ? response.status : undefined,
      requests: response.requests
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map(asUiRequestSummary),
    }
  }

  return undefined
}

export function updateUiResponseRequest(
  uiResponse: UiResponse,
  updatedRequest: UiRequestSummary,
  incomingUiResponse?: UiResponse,
): UiResponse {
  const next: UiResponse = { ...uiResponse, status: updatedRequest.review_status }

  if (uiResponse.request?.request_id === updatedRequest.request_id) {
    next.request = updatedRequest
  }

  if (uiResponse.requests?.length) {
    next.requests = uiResponse.requests.map((request) =>
      request.request_id === updatedRequest.request_id ? updatedRequest : request
    )
  }

  if (
    uiResponse.kind === CHAT_UI_RESPONSE_KIND.REQUEST_STATUS
    || uiResponse.kind === CHAT_UI_RESPONSE_KIND.REQUEST_SUBMITTED
  ) {
    next.title = `Request ${updatedRequest.request_id}`
  }

  if (incomingUiResponse?.body) next.body = incomingUiResponse.body

  if (incomingUiResponse?.title && incomingUiResponse.kind === uiResponse.kind) {
    next.title = incomingUiResponse.title
  }

  return next
}

export function isPendingReviewStatus(status: string) {
  return status === CHAT_REQUEST_STATUS.SUBMITTED || status === CHAT_REQUEST_STATUS.IN_REVIEW
}
