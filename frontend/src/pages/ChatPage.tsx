import { useCallback, useEffect, useRef, useState } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { StructuredRequestPayload, UiResponse } from '@/lib/chatTypes'
import ChatHeader from '@/components/chat/ChatHeader'
import ChatEmptyState from '@/components/chat/ChatEmptyState'
import ChatComposer from '@/components/chat/ChatComposer'
import TypingIndicator from '@/components/chat/TypingIndicator'
import MessageBubble from '@/components/chat/MessageBubble'
import StructuredAgentBubble from '@/components/chat/StructuredAgentBubble'
import { useWebSocket, type WsMessage } from '@/hooks/useWebSocket'
import type { User } from '@/App'

type Message = { role: 'user' | 'agent'; text: string; uiResponse?: UiResponse }
// Fallback fires only if backend is genuinely unresponsive (LLM timeout, crash, etc.)
// Sends description-only text so the agent can still respond without parsing raw code blocks
const STRUCTURED_FALLBACK_MS = 15_000

function responseToText(r: Record<string, unknown>): string {
  if (typeof r.message === 'string' && r.message) return r.message
  if (r.request && typeof r.request === 'object') return formatRequestResponse(r.request as Record<string, unknown>)
  if (Array.isArray(r.requests)) return formatRequestListResponse(r.requests as Record<string, unknown>[])
  if (typeof r.summary_message === 'string' && r.summary_message) return r.summary_message
  return JSON.stringify(r, null, 2)
}

function formatStructuredPreview(payload: StructuredRequestPayload): string {
  const parts: string[] = []
  const request = payload.request.trim()
  if (request) {
    parts.push(request)
  }

  const approver = payload.approver.trim()
  if (approver) {
    parts.push(`Approver: ${approver}`)
  }

  for (const [key, section] of Object.entries({ before: payload.before, after: payload.after }) as Array<
    ['before' | 'after', StructuredRequestPayload['before']]
  >) {
    if (!section.enabled || !section.value.trim()) continue
    const label = payload.mode === 'object_change'
      ? key === 'before' ? 'From' : 'To'
      : key === 'before' ? 'Before' : 'After'
    parts.push(`${label} (${section.format})`)
    parts.push(`\`\`\`${section.format}\n${section.value.replace(/\n$/, '')}\n\`\`\``)
  }

  return parts.join('\n\n').trim()
}

function formatRequestResponse(request: Record<string, unknown>): string {
  const requestId = typeof request.request_id === 'string' ? request.request_id : 'Request'
  const status = typeof request.review_status === 'string' ? request.review_status : ''
  const target = typeof request.target_label === 'string' ? request.target_label : ''
  const text = typeof request.request_text === 'string' ? request.request_text : ''
  const requester = typeof request.requester_handle === 'string' ? request.requester_handle : ''
  const approver = typeof request.approver_handle === 'string' ? request.approver_handle : ''
  const from = typeof request.change_from_summary === 'string' ? request.change_from_summary : ''
  const to = typeof request.change_to_summary === 'string' ? request.change_to_summary : ''
  const lines = [requestId]
  if (status) lines.push(`Status: ${status}`)
  if (target) lines.push(`Target: ${target}`)
  if (requester) lines.push(`Requester: ${requester}`)
  if (approver) lines.push(`Approver: ${approver}`)
  if (from) lines.push(`From: ${from}`)
  if (to) lines.push(`To: ${to}`)
  if (text.trim()) lines.push('', text)
  return lines.join('\n')
}

function formatRequestListResponse(requests: Record<string, unknown>[]): string {
  if (requests.length === 0) return 'No requests found.'
  return requests
    .map(request => {
      const requestId = typeof request.request_id === 'string' ? request.request_id : 'Request'
      const status = typeof request.review_status === 'string' ? request.review_status : ''
      const target = typeof request.target_label === 'string' ? request.target_label : ''
      return [requestId, status && `(${status})`, target].filter(Boolean).join(' ')
    })
    .join('\n')
}

function asUiRequestSummary(request: Record<string, unknown>) {
  return {
    request_id: typeof request.request_id === 'string' ? request.request_id : 'Request',
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
  }
}

function deriveUiResponse(
  response: Record<string, unknown>,
  incoming?: UiResponse,
): UiResponse | undefined {
  if (incoming) return incoming

  if (response.request && typeof response.request === 'object') {
    return {
      kind: 'request_status',
      title: `Request ${typeof response.request.request_id === 'string' ? response.request.request_id : ''}`.trim(),
      body: typeof response.summary_message === 'string' ? response.summary_message : undefined,
      status: typeof response.request.review_status === 'string' ? response.request.review_status : undefined,
      request: asUiRequestSummary(response.request as Record<string, unknown>),
    }
  }

  if (Array.isArray(response.requests)) {
    return {
      kind: 'request_list',
      title: typeof response.message === 'string' ? response.message.split('\n')[0] : 'Requests',
      body: typeof response.summary_message === 'string' ? response.summary_message : undefined,
      status: typeof response.status === 'string' ? response.status : undefined,
      requests: response.requests
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map(asUiRequestSummary),
    }
  }

  return undefined
}

export default function ChatPage({ user }: { user: User }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [composerFill, setComposerFill] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const fallbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearFallback = useCallback(() => {
    if (fallbackTimer.current) { clearTimeout(fallbackTimer.current); fallbackTimer.current = null }
  }, [])

  useEffect(() => () => clearFallback(), [clearFallback])

  const onMessage = useCallback((msg: WsMessage) => {
    clearFallback()
    if (msg.type === 'typing') {
      setIsTyping(true)
    } else if (msg.type === 'done') {
      setIsTyping(false)
      setMessages(p => [...p, {
        role: 'agent',
        text: responseToText(msg.response),
        uiResponse: deriveUiResponse(msg.response, msg.ui_response),
      }])
    } else if (msg.type === 'error') {
      setIsTyping(false)
      setMessages(p => [...p, { role: 'agent', text: `Error: ${msg.message}` }])
    }
  }, [])

  const { connected, send } = useWebSocket(onMessage)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, isTyping])

  const doSend = useCallback((payload: string | StructuredRequestPayload) => {
    if (!connected) return

    if (typeof payload === 'string') {
      const text = payload.trim()
      if (!text) return
      setMessages(p => [...p, { role: 'user', text }])
      send({ type: 'message', text })
      return
    }

    const preview = formatStructuredPreview(payload)
    if (!preview) return
    setMessages(p => [...p, { role: 'user', text: preview }])
    setIsTyping(true)
    send({ type: 'structured_message', draft: payload })
    // Fallback: if backend is genuinely unresponsive (LLM hang, crash), send a short
    // description-only text so the agent can still respond. Code blocks are omitted to
    // prevent the LLM from interpreting raw YAML values as business from/to data.
    const parts = [payload.request.trim(), payload.approver.trim() ? `Approver: ${payload.approver.trim()}` : ''].filter(Boolean)
    if (parts.length) {
      clearFallback()
      fallbackTimer.current = setTimeout(() => send({ type: 'message', text: parts.join('\n') }), STRUCTURED_FALLBACK_MS)
    }
  }, [connected, send, clearFallback])

  return (
    <TooltipProvider delayDuration={350}>
      <div className="flex h-screen flex-col bg-background">

        <ChatHeader
          connected={connected}
          hasMessages={messages.length > 0}
          user={user}
          onClear={() => setMessages([])}
        />

        <div className="flex-1 overflow-y-auto bg-chat-bg px-4 py-6">
          {messages.length === 0 ? (
            <ChatEmptyState connected={connected} onFill={setComposerFill} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {messages.map((m, i) =>
                m.role === 'agent' && m.uiResponse ? (
                  <StructuredAgentBubble key={i} fallbackText={m.text} uiResponse={m.uiResponse} />
                ) : (
                  <MessageBubble key={i} role={m.role} text={m.text} />
                )
              )}
              {isTyping && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <ChatComposer
          connected={connected}
          onSend={doSend}
          fillText={composerFill}
          onFillConsumed={() => setComposerFill('')}
        />

      </div>
    </TooltipProvider>
  )
}
