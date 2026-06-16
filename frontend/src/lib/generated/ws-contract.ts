/* eslint-disable */
/* This file is auto-generated from contracts/asyncapi.yaml — do not edit by hand */
/**
 * Format of a code section or request body.
 */
export type CodeFormat = 'text' | 'yaml' | 'json';
/**
 * How the change request is structured.
 */
export type RequestMode = 'free_text' | 'config_change' | 'object_change';

/**
 * Free-text chat message from the user.
 */
export interface WsTextMessage {
  type: 'message';
  text: string;
}
/**
 * A code block with format metadata.
 */
export interface StructuredCodeSection {
  enabled: boolean;
  format: CodeFormat;
  value: string;
}
/**
 * Full structured change request payload.
 */
export interface StructuredRequestPayload {
  mode: RequestMode;
  request_format: CodeFormat;
  request: string;
  approver: string;
  before: StructuredCodeSection;
  after: StructuredCodeSection;
}
/**
 * Structured request form submitted by the user.
 */
export interface WsStructuredMessage {
  type: 'structured_message';
  draft: StructuredRequestPayload;
}
/**
 * User confirms or discards a pending draft.
 */
export interface WsActionMessage {
  type: 'action';
  op: 'confirm' | 'discard';
}
/**
 * Agent is processing — show typing indicator.
 */
export interface WsTypingMessage {
  type: 'typing';
}
/**
 * Summary of a single change request for UI display.
 */
export interface UiRequestSummary {
  request_id: string;
  requester_handle: string;
  approver_handle: string;
  target_label: string;
  change_from_summary: string;
  change_to_summary: string;
  review_status: string;
  request_text: string;
  structured_payload: StructuredRequestPayload | null;
}
/**
 * Structured UI response envelope returned inside a done message.
 */
export interface UiResponse {
  kind: string;
  title?: string | null;
  body?: string | null;
  status?: string | null;
  request?: UiRequestSummary | null;
  requests?: UiRequestSummary[] | null;
}
/**
 * Agent has finished processing and returns a response.
 */
export interface WsDoneMessage {
  type: 'done';
  response: {
    [k: string]: unknown;
  };
  ui_response?: UiResponse | null;
}
/**
 * An error occurred during processing.
 */
export interface WsErrorMessage {
  type: 'error';
  message: string;
}
