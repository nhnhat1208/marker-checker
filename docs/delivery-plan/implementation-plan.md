# Implementation Plan

## Goal

Deliver one useful approval workflow with:

- request creation
- approver decision
- lookup by request ID
- audit history

## Scope To Keep

- one runtime
- one Telegram adapter
- one Google Sheets backend
- one approver per request
- optional LLM assistance

## Scope To Defer

- web UI
- group chat workflow
- RBAC
- reminder automation
- AI diff analysis
- multiple channel adapters

## Milestones

### 1. Core Request Flow

- parse request
- show normalized summary
- require `/confirm`
- create request and audit events

### 2. Review Flow

- approve
- reject
- need info
- cancel
- resubmit

### 3. Lookup And Audit

- status lookup
- history lookup
- readable summary output

### 4. Stabilization

- config validation
- persistence validation
- transition guard validation
- deploy verification

## Delivery Checklist

### External Setup

- AgentBase IAM works
- Telegram bot token is ready
- Google Sheet and service account are ready

### Local Validation

- runtime starts
- worksheets are created
- request flow works
- approval flow works
- lookup and history work

### Deploy Validation

- image builds
- runtime becomes `ACTIVE`
- health endpoint returns `200`
- Telegram and spreadsheet work after deploy

## Main Risks

- ambiguous request text
- ambiguous request context
- Google Sheets concurrency limits
- credential misconfiguration

## Mitigation

- keep one preferred request pattern
- prefer explicit request ID for state changes
- keep one runtime replica
- validate config at startup
