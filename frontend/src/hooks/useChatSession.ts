import { useCallback, useEffect, useRef, useState } from 'react'
import type { StructuredRequestPayload } from '@/lib/chatTypes'
import {
  applyIncomingAgentMessage,
  CHAT_DRAFT_ACTION,
  CHAT_MESSAGE_ROLE,
  CHAT_PENDING_ACTION_KIND,
  CHAT_TIMING,
  type ChatMessage,
  deriveUiResponse,
  formatStructuredPreview,
  type PendingAction,
  responseToText,
  type ReviewAction,
  type DraftAction,
} from '@/lib/chatUi'
import { useWebSocket, type WsMessage } from '@/hooks/useWebSocket'

function isDuplicateWithinWindow(
  store: Map<string, number>,
  text: string,
  windowMs: number,
) {
  const normalized = text.trim()
  if (!normalized) return false

  const now = Date.now()
  for (const [key, timestamp] of store.entries()) {
    if (now - timestamp > windowMs) {
      store.delete(key)
    }
  }

  const previous = store.get(normalized)
  store.set(normalized, now)
  return previous !== undefined && now - previous <= windowMs
}

export function useChatSession() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [actionPending, setActionPending] = useState(false)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [composerFill, setComposerFill] = useState('')

  const fallbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const recentPlainAgentMessages = useRef<Map<string, number>>(new Map())
  const pendingActionRef = useRef<PendingAction | null>(null)

  const setPendingActionState = useCallback((value: PendingAction | null) => {
    pendingActionRef.current = value
    setPendingAction(value)
  }, [])

  const clearFallback = useCallback(() => {
    if (fallbackTimer.current) {
      clearTimeout(fallbackTimer.current)
      fallbackTimer.current = null
    }
  }, [])

  useEffect(() => () => clearFallback(), [clearFallback])

  const onMessage = useCallback((msg: WsMessage) => {
    clearFallback()

    if (msg.type === 'typing') {
      setIsTyping(true)
      return
    }

    if (msg.type === 'done') {
      setIsTyping(false)
      setActionPending(false)

      const currentPendingAction = pendingActionRef.current
      setPendingActionState(null)

      const nextUiResponse = deriveUiResponse(msg.response, msg.ui_response)
      const nextText = responseToText(msg.response)

      if (
        !nextUiResponse
        && isDuplicateWithinWindow(
          recentPlainAgentMessages.current,
          nextText,
          CHAT_TIMING.PLAIN_AGENT_DEDUPE_WINDOW_MS,
        )
      ) {
        return
      }

      setMessages((previous) => applyIncomingAgentMessage({
        messages: previous,
        pendingAction: currentPendingAction,
        nextText,
        nextUiResponse,
      }))
      return
    }

    if (msg.type === 'error') {
      setIsTyping(false)
      setActionPending(false)
      setPendingActionState(null)

      const errorText = `Error: ${msg.message}`
      if (
        isDuplicateWithinWindow(
          recentPlainAgentMessages.current,
          errorText,
          CHAT_TIMING.PLAIN_AGENT_DEDUPE_WINDOW_MS,
        )
      ) {
        return
      }

      setMessages((previous) => [
        ...previous,
        { role: CHAT_MESSAGE_ROLE.AGENT, text: errorText, timestamp: Date.now() },
      ])
    }
  }, [clearFallback, setPendingActionState])

  const { connected, send } = useWebSocket(onMessage)

  useEffect(() => {
    if (!connected) {
      setActionPending(false)
      setPendingActionState(null)
    }
  }, [connected, setPendingActionState])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  const pushUserMessage = useCallback((text: string) => {
    setMessages((previous) => [
      ...previous,
      { role: CHAT_MESSAGE_ROLE.USER, text, timestamp: Date.now() },
    ])
  }, [])

  const sendDraftAction = useCallback((op: DraftAction) => {
    if (!connected || actionPending) return

    setActionPending(true)
    setPendingActionState({ kind: CHAT_PENDING_ACTION_KIND.DRAFT, op })
    setIsTyping(true)
    send({ type: 'action', op })
  }, [actionPending, connected, send, setPendingActionState])

  const sendReviewAction = useCallback((
    action: ReviewAction,
    requestId: string,
    note = '',
  ) => {
    if (!connected || actionPending) return

    setActionPending(true)
    setPendingActionState({
      kind: CHAT_PENDING_ACTION_KIND.REVIEW,
      op: action,
      requestId,
    })
    setIsTyping(true)
    send({
      type: 'action',
      op: action,
      request_id: requestId,
      note: note.trim() || undefined,
    })
  }, [actionPending, connected, send, setPendingActionState])

  const sendPayload = useCallback((payload: string | StructuredRequestPayload) => {
    if (!connected) return

    if (typeof payload === 'string') {
      const text = payload.trim()
      if (!text) return

      pushUserMessage(text)
      setIsTyping(true)
      send({ type: 'message', text })
      return
    }

    const preview = formatStructuredPreview(payload)
    if (!preview) return

    pushUserMessage(preview)
    setIsTyping(true)
    send({ type: 'structured_message', draft: payload })

    const fallbackParts = [
      payload.request.trim(),
      payload.approver.trim() ? `Approver: ${payload.approver.trim()}` : '',
    ].filter(Boolean)

    if (fallbackParts.length) {
      clearFallback()
      fallbackTimer.current = setTimeout(
        () => send({ type: 'message', text: fallbackParts.join('\n') }),
        CHAT_TIMING.STRUCTURED_FALLBACK_MS,
      )
    }
  }, [clearFallback, connected, pushUserMessage, send])

  return {
    actionPending,
    clearMessages,
    composerFill,
    connected,
    isTyping,
    messages,
    pendingAction,
    sendDraftAction,
    sendPayload,
    sendReviewAction,
    setComposerFill,
  }
}
