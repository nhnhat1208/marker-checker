import type { UiResponse } from '@/lib/chatTypes'
import {
  CHAT_MESSAGE_ROLE,
  CHAT_PENDING_ACTION_KIND,
  CHAT_UI_RESPONSE_KIND,
  type ChatMessage,
  type PendingAction,
} from './constants'
import { updateUiResponseRequest } from './response'

export function findLastActionableAgentIndex(
  messages: ChatMessage[],
  predicate: (message: ChatMessage) => boolean,
) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (predicate(messages[index])) return index
  }
  return -1
}

export function applyIncomingAgentMessage({
  messages,
  pendingAction,
  nextText,
  nextUiResponse,
}: {
  messages: ChatMessage[]
  pendingAction: PendingAction | null
  nextText: string
  nextUiResponse?: UiResponse
}): ChatMessage[] {
  const updatedRequest = nextUiResponse?.request

  if (pendingAction?.kind === CHAT_PENDING_ACTION_KIND.DRAFT) {
    const draftIndex = findLastActionableAgentIndex(
      messages,
      (message) =>
        message.role === CHAT_MESSAGE_ROLE.AGENT
        && message.uiResponse?.kind === CHAT_UI_RESPONSE_KIND.CONFIRMATION_REQUIRED,
    )
    if (draftIndex >= 0) {
      const next = [...messages]
      const nextMessage: ChatMessage = {
        ...messages[draftIndex],
        role: CHAT_MESSAGE_ROLE.AGENT,
        text: nextText,
        timestamp: messages[draftIndex].timestamp,
      }
      if (nextUiResponse) {
        nextMessage.uiResponse = nextUiResponse
      } else {
        delete nextMessage.uiResponse
      }
      next[draftIndex] = nextMessage
      return next
    }
  }

  if (pendingAction?.kind === CHAT_PENDING_ACTION_KIND.REVIEW && updatedRequest) {
    let transformed = false
    const next = messages.map((message) => {
      if (message.role !== CHAT_MESSAGE_ROLE.AGENT || !message.uiResponse) return message

      const matchesRequest =
        message.uiResponse.request?.request_id === pendingAction.requestId
        || Boolean(
          message.uiResponse.requests?.some((request) => request.request_id === pendingAction.requestId),
        )

      if (!matchesRequest) return message

      transformed = true
      return {
        ...message,
        text: nextText,
        timestamp: message.timestamp,
        uiResponse: updateUiResponseRequest(message.uiResponse, updatedRequest, nextUiResponse),
      }
    })

    if (transformed) return next
  }

  const merged = updatedRequest
    ? messages.map((message) =>
        message.role === CHAT_MESSAGE_ROLE.AGENT && message.uiResponse
          ? { ...message, uiResponse: updateUiResponseRequest(message.uiResponse, updatedRequest, nextUiResponse) }
          : message
      )
    : messages

  return [
    ...merged,
    {
      role: CHAT_MESSAGE_ROLE.AGENT,
      text: nextText,
      timestamp: Date.now(),
      uiResponse: nextUiResponse,
    },
  ]
}
