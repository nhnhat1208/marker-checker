import { Highlight, themes } from 'prism-react-renderer'
import { cn } from '@/lib/utils'
import { useTheme } from '@/contexts/theme'

type Props = {
  content: string
  language: string
  tone: 'before' | 'after' | 'neutral'
  label: string
}

export default function CodeBlock({ content, language, tone, label }: Props) {
  const { theme } = useTheme()
  const prismTheme = theme === 'dark' ? themes.oneDark : themes.github

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div
        className={cn(
          'border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest',
          tone === 'before'
            ? 'border-rose-100 bg-rose-50 text-rose-600 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-400'
            : tone === 'after'
              ? 'border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-400'
              : 'border-border bg-muted/50 text-muted-foreground',
        )}
      >
        {label}
        <span className="ml-2 font-normal normal-case tracking-normal opacity-60">{language}</span>
      </div>

      <Highlight theme={prismTheme} code={content.replace(/\n$/, '')} language={language}>
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre
            style={{
              ...style,
              margin: 0,
              padding: '12px 16px',
              fontSize: '12px',
              lineHeight: '1.6',
              overflow: 'auto',
              borderRadius: 0,
            }}
          >
            {tokens.map((line, index) => (
              <div key={index} {...getLineProps({ line })}>
                {line.map((token, tokenIndex) => (
                  <span key={tokenIndex} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  )
}
