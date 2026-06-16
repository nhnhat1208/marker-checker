import type { StructuredRequestPayload } from '@/lib/chatTypes'
import { CHAT_COPY } from './constants'

function normalizeStatusLabel(status: string) {
  const key = status.trim().toLowerCase().replace(/[_\s]+/g, ' ')
  switch (key) {
    case 'submitted':
      return 'Pending'
    case 'in review':
      return 'In review'
    case 'approved':
      return 'Approved'
    case 'rejected':
      return 'Rejected'
    case 'cancelled':
      return 'Cancelled'
    case 'needs info':
      return 'Needs info'
    case 'draft':
      return 'Draft'
    case 'error':
      return 'Error'
    default:
      return status
  }
}

function formatRequestResponse(request: Record<string, unknown>): string {
  const requestId = typeof request.request_id === 'string' ? request.request_id : CHAT_COPY.REQUEST_FALLBACK_TITLE
  const status = typeof request.review_status === 'string' ? request.review_status : ''
  const target = typeof request.target_label === 'string' ? request.target_label : ''
  const text = typeof request.request_text === 'string' ? request.request_text : ''
  const requester = typeof request.requester_handle === 'string' ? request.requester_handle : ''
  const approver = typeof request.approver_handle === 'string' ? request.approver_handle : ''
  const from = typeof request.change_from_summary === 'string' ? request.change_from_summary : ''
  const to = typeof request.change_to_summary === 'string' ? request.change_to_summary : ''
  const lines = [requestId]

  if (status) lines.push(`Current: ${normalizeStatusLabel(status)}`)
  if (target) lines.push(`Target: ${target}`)
  if (requester) lines.push(`Requester: ${requester}`)
  if (approver) lines.push(`Approver: ${approver}`)
  if (from) lines.push(`Current state: ${from}`)
  if (to) lines.push(`Proposed state: ${to}`)
  if (text.trim()) lines.push('', text)

  return lines.join('\n')
}

function formatRequestListResponse(requests: Record<string, unknown>[]): string {
  if (requests.length === 0) return CHAT_COPY.NO_REQUESTS_FOUND

  return requests
    .map((request) => {
      const requestId = typeof request.request_id === 'string' ? request.request_id : CHAT_COPY.REQUEST_FALLBACK_TITLE
      const status = typeof request.review_status === 'string' ? request.review_status : ''
      const target = typeof request.target_label === 'string' ? request.target_label : ''
      const normalizedStatus = status ? normalizeStatusLabel(status) : ''
      return [requestId, normalizedStatus && `(${normalizedStatus})`, target].filter(Boolean).join(' ')
    })
    .join('\n')
}

function getSectionLabel(payload: StructuredRequestPayload, key: 'before' | 'after') {
  if (payload.mode === 'object_change') {
    return key === 'before' ? 'Before change' : 'After change'
  }
  return key === 'before' ? 'Before' : 'After'
}

export function responseToText(response: Record<string, unknown>): string {
  if (typeof response.message === 'string' && response.message) return response.message
  if (response.request && typeof response.request === 'object') {
    return formatRequestResponse(response.request as Record<string, unknown>)
  }
  if (Array.isArray(response.requests)) {
    return formatRequestListResponse(response.requests as Record<string, unknown>[])
  }
  if (typeof response.summary_message === 'string' && response.summary_message) {
    return response.summary_message
  }
  return JSON.stringify(response, null, 2)
}

export function formatStructuredPreview(payload: StructuredRequestPayload): string {
  const parts: string[] = []
  const request = payload.request.trim()
  const approver = payload.approver.trim()

  if (request) parts.push(request)
  if (approver) parts.push(`Approver: ${approver}`)

  for (const [key, section] of Object.entries({
    before: payload.before,
    after: payload.after,
  }) as Array<['before' | 'after', StructuredRequestPayload['before']]>) {
    if (!section.enabled || !section.value.trim()) continue
    parts.push(`${getSectionLabel(payload, key)} (${section.format})`)
    parts.push(`\`\`\`${section.format}\n${section.value.replace(/\n$/, '')}\n\`\`\``)
  }

  return parts.join('\n\n').trim()
}
