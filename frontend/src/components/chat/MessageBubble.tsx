import { type ReactNode } from 'react'
import { Highlight, themes } from 'prism-react-renderer'
import { cn } from '@/lib/utils'
import { useTheme } from '@/contexts/theme'
import CodeDiffPreview from './CodeDiffPreview'

type Props = {
  role: 'user' | 'agent'
  text: string
}

type Segment =
  | { type: 'text'; content: string }
  | { type: 'code'; content: string; language: string }

type CodeLabel = {
  language: string
  title: 'Before' | 'After' | 'From' | 'To'
}

function parseSegments(text: string): Segment[] {
  const segments: Segment[] = []
  const pattern = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g
  let lastIndex = 0

  for (const match of text.matchAll(pattern)) {
    const matchIndex = match.index ?? 0
    if (matchIndex > lastIndex) segments.push({ type: 'text', content: text.slice(lastIndex, matchIndex) })
    segments.push({ type: 'code', language: match[1] ?? 'text', content: match[2].replace(/\n$/, '') })
    lastIndex = matchIndex + match[0].length
  }

  if (lastIndex < text.length) segments.push({ type: 'text', content: text.slice(lastIndex) })
  return segments.length > 0 ? segments : [{ type: 'text', content: text }]
}

function renderTextSegment(content: string, isUser: boolean) {
  const trimmed = content.replace(/^\n+|\n+$/g, '')
  if (!trimmed) return null
  return (
    <div className={cn('whitespace-pre-wrap text-sm leading-7', isUser ? 'text-primary-foreground' : 'text-foreground')}>
      {trimmed}
    </div>
  )
}

/* ── Syntax-highlighted code block ── */
function CodeBlockCard({ content, language }: { content: string; language: string }) {
  const { theme } = useTheme()
  const prismTheme = theme === 'dark' ? themes.oneDark : themes.github

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      {/* Header */}
      <div className={cn(
        'flex items-center justify-between border-b border-border bg-muted/50 px-3 py-2',
      )}>
        <span className="font-mono text-[11px] font-semibold text-muted-foreground">{language}</span>
        <span className="text-[11px] text-muted-foreground/60">code block</span>
      </div>

      <Highlight theme={prismTheme} code={content.replace(/\n$/, '')} language={language}>
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre style={{ ...style, margin: 0, padding: '12px 16px', fontSize: '12px', lineHeight: '1.6', overflow: 'auto', borderRadius: 0 }}>
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  )
}

function splitTrailingLabel(content: string) {
  const match = content.match(/^(.*?)(?:\n\s*\n)?(Before|After|From|To) \((yaml|json)\)\s*$/s)
  if (!match) return { leadingText: content, label: null as CodeLabel | null }
  return {
    leadingText: match[1],
    label: { title: match[2] as CodeLabel['title'], language: match[3] },
  }
}

function splitLeadingLabel(content: string) {
  const match = content.match(/^\s*(Before|After|From|To) \((yaml|json)\)\s*([\s\S]*)$/)
  if (!match) return { trailingText: content, label: null as CodeLabel | null }
  return {
    trailingText: match[3],
    label: { title: match[1] as CodeLabel['title'], language: match[2] },
  }
}

function isPair(first: CodeLabel | null, second: CodeLabel | null) {
  if (!first || !second) return false
  return (
    ((first.title === 'Before' && second.title === 'After') ||
      (first.title === 'From' && second.title === 'To')) &&
    first.language === second.language
  )
}

export default function MessageBubble({ role, text }: Props) {
  const isUser = role === 'user'
  const segments = parseSegments(text)
  const renderedSegments: ReactNode[] = []

  for (let index = 0; index < segments.length; index++) {
    const current = segments[index]
    const next  = segments[index + 1]
    const third = segments[index + 2]
    const fourth = segments[index + 3]

    if (
      current?.type === 'text' &&
      next?.type === 'code' &&
      third?.type === 'text' &&
      fourth?.type === 'code'
    ) {
      const first  = splitTrailingLabel(current.content)
      const second = splitLeadingLabel(third.content)

      if (isPair(first.label, second.label)) {
        const leadingText = renderTextSegment(first.leadingText, isUser)
        if (leadingText) renderedSegments.push(<div key={`lead-${index}`}>{leadingText}</div>)

        renderedSegments.push(
          <CodeDiffPreview
            key={`diff-${index}`}
            beforeContent={next.content}
            afterContent={fourth.content}
            beforeLabel={first.label!.title}
            afterLabel={second.label!.title}
            format={first.label!.language}
            showRawToggle
          />,
        )

        const trailingText = renderTextSegment(second.trailingText, isUser)
        if (trailingText) renderedSegments.push(<div key={`trail-${index}`}>{trailingText}</div>)

        index += 3
        continue
      }
    }

    if (current.type === 'text') {
      renderedSegments.push(<div key={`text-${index}`}>{renderTextSegment(current.content, isUser)}</div>)
      continue
    }

    renderedSegments.push(
      <CodeBlockCard key={`code-${index}`} content={current.content} language={current.language} />,
    )
  }

  return (
    <div className={cn('flex items-start gap-2.5', isUser && 'flex-row-reverse')}>
      {!isUser && (
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary shadow-sm">
          <span className="select-none text-xs font-bold text-primary-foreground">M</span>
        </div>
      )}

      <div className={cn(
        'max-w-[min(100%,56rem)] rounded-2xl px-4 py-3',
        isUser
          ? 'bg-primary text-primary-foreground rounded-tr-sm shadow-md'
          : 'rounded-tl-sm border border-border/80 bg-background text-foreground shadow-lg',
      )}>
        <div className="space-y-3">{renderedSegments}</div>
      </div>
    </div>
  )
}
