import { useCallback, useEffect, useRef, useState } from 'react'
import type { WsClientMessage, WsServerMessage } from '@/lib/chatTypes'

export type WsMessage = WsServerMessage

export function useWebSocket(onMessage: (msg: WsMessage) => void) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttempts = useRef(0)
  const shouldReconnect = useRef(true)
  const socketGeneration = useRef(0)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (!shouldReconnect.current) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws/chat`)
    const generation = ++socketGeneration.current
    wsRef.current = ws

    ws.onopen = () => {
      if (!shouldReconnect.current || generation !== socketGeneration.current) {
        ws.close()
        return
      }
      reconnectAttempts.current = 0
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      setConnected(true)
    }
    ws.onclose = () => {
      if (generation !== socketGeneration.current) return
      if (wsRef.current === ws) {
        wsRef.current = null
      }
      setConnected(false)
      if (!shouldReconnect.current) return

      // Reconnect with exponential backoff (1s → 30s)
      const delay = Math.min(30000, 1000 * 2 ** reconnectAttempts.current)
      reconnectAttempts.current += 1
      reconnectTimer.current = setTimeout(() => {
        reconnectTimer.current = null
        connect()
      }, delay)
    }
    ws.onmessage = (e: MessageEvent<string>) => {
      if (generation !== socketGeneration.current) return
      try {
        const msg = JSON.parse(e.data) as WsMessage
        onMessageRef.current(msg)
      } catch {
        // ignore malformed frames
      }
    }
  }, [])

  useEffect(() => {
    shouldReconnect.current = true
    connect()
    return () => {
      shouldReconnect.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
      reconnectAttempts.current = 0
      const ws = wsRef.current
      wsRef.current = null
      ws?.close()
      setConnected(false)
    }
  }, [connect])

  const send = useCallback((payload: WsClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    }
  }, [])

  return { connected, send }
}
