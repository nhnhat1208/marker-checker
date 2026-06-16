import { useEffect, useRef, useState } from 'react'
import { X, Check } from 'lucide-react'
import ReactCodeMirror from '@uiw/react-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { json } from '@codemirror/lang-json'
import { githubDark, githubLight } from '@uiw/codemirror-theme-github'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useTheme } from '@/contexts/theme'
import {
  EDITOR_LANGUAGE,
  LANGUAGE_GROUPS,
  type EditorLanguage,
} from '@/lib/chatComposerConfig'

function getExtension(lang: EditorLanguage) {
  if (lang === EDITOR_LANGUAGE.YAML) return [yaml()]
  if (lang === EDITOR_LANGUAGE.JSON) return [json()]
  return []
}

function LanguagePicker({
  value,
  onChange,
}: {
  value: EditorLanguage
  onChange: (lang: EditorLanguage) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {LANGUAGE_GROUPS.flatMap((group) => group.langs).map((lang) => (
        <button
          key={lang.value}
          type="button"
          onClick={() => onChange(lang.value)}
          className={cn(
            'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
            value === lang.value
              ? 'border-primary/20 bg-primary text-primary-foreground'
              : 'border-border bg-background text-muted-foreground hover:text-foreground',
          )}
        >
          {lang.label}
        </button>
      ))}
    </div>
  )
}

function CodeEditor({
  value,
  onChange,
  label,
  tone,
  language,
}: {
  value: string
  onChange: (v: string) => void
  label: string
  tone: 'before' | 'after'
  language: EditorLanguage
}) {
  const { theme } = useTheme()

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-border bg-background">
      <div
        className={cn(
          'border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest select-none',
          tone === 'before'
            ? 'border-rose-100/70 bg-rose-50/70 text-rose-700 dark:border-rose-900/30 dark:bg-rose-950/20 dark:text-rose-300'
            : 'border-emerald-100/70 bg-emerald-50/70 text-emerald-700 dark:border-emerald-900/30 dark:bg-emerald-950/20 dark:text-emerald-300',
        )}
      >
        {label}
      </div>
      <ReactCodeMirror
        value={value}
        onChange={(val) => onChange(val)}
        theme={theme === 'dark' ? githubDark : githubLight}
        extensions={getExtension(language)}
        minHeight="8rem"
        maxHeight="16rem"
        placeholder={language === EDITOR_LANGUAGE.TEXT ? 'Plain text here…' : `# ${language} here…`}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          dropCursor: true,
          highlightActiveLine: true,
          highlightSelectionMatches: false,
          bracketMatching: true,
          closeBrackets: true,
          autocompletion: false,
        }}
        style={{ fontSize: '12px' }}
      />
    </div>
  )
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  before: string
  after: string
  language: EditorLanguage
  onSave: (next: { before: string; after: string; language: EditorLanguage }) => void
  onClear: () => void
}

export default function CodeChangesDialog({
  open,
  onOpenChange,
  before,
  after,
  language,
  onSave,
  onClear,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null)
  const hasAttachedCode = Boolean(before.trim() || after.trim())
  const [draftBefore, setDraftBefore] = useState(before)
  const [draftAfter, setDraftAfter] = useState(after)
  const [draftLanguage, setDraftLanguage] = useState<EditorLanguage>(language)

  useEffect(() => {
    if (!open) return
    setDraftBefore(before)
    setDraftAfter(after)
    setDraftLanguage(language)
  }, [before, after, language, open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onOpenChange(false)
    }
    const onMouseDown = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) onOpenChange(false)
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('mousedown', onMouseDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('mousedown', onMouseDown)
    }
  }, [open, onOpenChange])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-3 py-3 sm:items-center sm:px-6">
      <div
        ref={panelRef}
        className="w-full max-w-4xl overflow-hidden rounded-3xl border border-border bg-background shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-border/70 px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Attach code changes</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Optional. Save when you want to include a config or code diff with the request.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-4 py-4 sm:px-5">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Language</p>
              <p className="mt-1 text-xs text-muted-foreground/70">Pick the format that matches the diff.</p>
            </div>
            <LanguagePicker value={draftLanguage} onChange={setDraftLanguage} />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <CodeEditor value={draftBefore} onChange={setDraftBefore} label="Before" tone="before" language={draftLanguage} />
            <CodeEditor value={draftAfter} onChange={setDraftAfter} label="After" tone="after" language={draftLanguage} />
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-border/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-muted-foreground">
            Saved diff will be attached to the request composer.
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                if (hasAttachedCode) {
                  onClear()
                  return
                }
                onOpenChange(false)
              }}
            >
              {hasAttachedCode ? 'Remove' : 'Cancel'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onSave({
                  before: draftBefore,
                  after: draftAfter,
                  language: draftLanguage,
                })
                onOpenChange(false)
              }}
              className="border-primary/20 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Check className="h-4 w-4" />
              Save
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
