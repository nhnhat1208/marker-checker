import type {
  StructuredCodeSection,
  StructuredRequestPayload,
  UiDraftSummary,
  UiRequestSummary,
  UiResponse,
  WsActionMessage,
  WsDoneMessage,
  WsErrorMessage,
  WsStructuredMessage,
  WsTextMessage,
  WsTypingMessage,
} from './generated/ws-contract'

export type {
  StructuredCodeSection,
  StructuredRequestPayload,
  UiDraftSummary,
  UiRequestSummary,
  UiResponse,
  WsActionMessage,
  WsDoneMessage,
  WsErrorMessage,
  WsStructuredMessage,
  WsTextMessage,
  WsTypingMessage,
}

export type DraftSection = StructuredCodeSection
export type CodeFormat = StructuredCodeSection['format']
export type RequestMode = StructuredRequestPayload['mode']
export type WsClientMessage = WsTextMessage | WsStructuredMessage | WsActionMessage
export type WsServerMessage = WsTypingMessage | WsDoneMessage | WsErrorMessage
