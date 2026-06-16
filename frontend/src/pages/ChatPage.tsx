import { useEffect, useRef } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import ChatComposer from '@/components/chat/ChatComposer'
import ChatEmptyState from '@/components/chat/ChatEmptyState'
import ChatHeader from '@/components/chat/ChatHeader'
import MessageBubble from '@/components/chat/MessageBubble'
import StructuredAgentBubble from '@/components/chat/StructuredAgentBubble'
import TypingIndicator from '@/components/chat/TypingIndicator'
import { useChatSession } from '@/hooks/useChatSession'
import { CHAT_MESSAGE_ROLE } from '@/lib/chatUi'
import type { User } from '@/App'

export default function ChatPage({ user }: { user: User }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const composerAnchorRef = useRef<HTMLDivElement>(null)
  const {
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
  } = useChatSession()

  const appendMissingInfoToComposer = (text: string) => {
    const suggestion = text.trim()
    if (!suggestion) return

    setComposerFill((previous) => {
      const current = previous.trim()
      if (current) return `${current}\n\n${suggestion}`
      return suggestion
    })
  }

  const hasLaterUserReply = (messageIndex: number) =>
    messages.slice(messageIndex + 1).some((message) => message.role === CHAT_MESSAGE_ROLE.USER)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  useEffect(() => {
    if (!composerFill) return
    composerAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [composerFill])

  return (
    <TooltipProvider delayDuration={350}>
      <div className="flex h-screen flex-col bg-background">
        <ChatHeader
          connected={connected}
          hasMessages={messages.length > 0}
          user={user}
          onClear={clearMessages}
        />

        <div className="flex-1 overflow-y-auto bg-chat-bg px-4 py-6">
          {messages.length === 0 ? (
            <ChatEmptyState connected={connected} onFill={setComposerFill} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {messages.map((message, index) =>
                message.role === CHAT_MESSAGE_ROLE.AGENT && message.uiResponse ? (
                  <StructuredAgentBubble
                    key={index}
                    fallbackText={message.text}
                    uiResponse={message.uiResponse}
                    timestamp={message.timestamp}
                    viewerHandle={user.email}
                    missingInfoActionHidden={hasLaterUserReply(index)}
                    actionPending={actionPending}
                    pendingAction={pendingAction}
                    onDraftAction={sendDraftAction}
                    onReviewAction={sendReviewAction}
                    onMissingFieldClick={appendMissingInfoToComposer}
                  />
                ) : (
                  <MessageBubble
                    key={index}
                    role={message.role}
                    text={message.text}
                    timestamp={message.timestamp}
                    userName={user.name || user.email}
                    userAvatarUrl={user.avatar_url}
                  />
                )
              )}
              {isTyping && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div ref={composerAnchorRef}>
          <ChatComposer
            connected={connected}
            onSend={sendPayload}
            fillText={composerFill}
            onFillConsumed={() => setComposerFill('')}
          />
        </div>
      </div>
    </TooltipProvider>
  )
}
