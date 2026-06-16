import { useEffect, useMemo, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

type Example = {
  category: string
  categoryLabel: string
  labelEn: string
  labelVi: string
  en: string
  vi: string
}

function parseExamples(md: string): Example[] {
  const result: Example[] = []
  const sections = ('\n' + md).split(/\n## /).slice(1)
  for (const section of sections) {
    const lines = section.split('\n')
    const categoryLabel = lines[0].trim()
    const categoryId = categoryLabel.toLowerCase()
    const exSections = lines.slice(1).join('\n').split(/\n### /).slice(1)
    for (const ex of exSections) {
      const exLines = ex.trim().split('\n').filter(Boolean)
      if (exLines.length < 2) continue
      const labelParts = exLines[0].split(' / ')
      const labelEn = labelParts[0].trim()
      const labelVi = labelParts[1]?.trim() || labelEn
      let en = ''
      let vi = ''
      for (const line of exLines.slice(1)) {
        if (line.startsWith('en: ')) en = line.slice(4).trim()
        else if (line.startsWith('vi: ')) vi = line.slice(4).trim()
        else if (!en) en = line.trim()
      }
      if (!vi) vi = en
      if (en) result.push({ category: categoryId, categoryLabel, labelEn, labelVi, en, vi })
    }
  }
  return result
}

type Props = {
  connected: boolean
  onFill: (text: string) => void
}

export default function ChatEmptyState({ connected, onFill }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'vi' ? 'vi' : 'en'
  const [examples, setExamples] = useState<Example[]>([])
  const [activeCategory, setActiveCategory] = useState('all')

  useEffect(() => {
    fetch('/examples.md')
      .then(r => r.text())
      .then(md => setExamples(parseExamples(md)))
      .catch(() => {})
  }, [])

  const categories = useMemo(() => [
    { id: 'all', label: t('empty.all') },
    ...Array.from(
      new Map(examples.map(e => [e.category, e.categoryLabel])).entries()
    ).map(([id, label]) => ({ id, label })),
  ], [examples, t])

  const filtered = activeCategory === 'all'
    ? examples
    : examples.filter(e => e.category === activeCategory)

  return (
    <div className="mx-auto mt-8 max-w-lg text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary shadow-md">
        <span className="select-none text-2xl font-bold text-primary-foreground">M</span>
      </div>
      <h2 className="mb-1 text-lg font-semibold text-foreground">{t('empty.headline')}</h2>
      <p className="mb-5 text-sm text-muted-foreground">{t('empty.subtitle')}</p>

      {/* Category filter */}
      {categories.length > 1 && (
        <div className="mb-3 flex flex-wrap justify-center gap-1.5">
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                activeCategory === cat.id
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'bg-muted text-muted-foreground hover:text-foreground',
              )}
            >
              {cat.label}
            </button>
          ))}
        </div>
      )}

      {/* Example list */}
      <div className="space-y-2 text-left">
        {filtered.map((ex, i) => (
          <button
            key={i}
            disabled={!connected}
            onClick={() => onFill(ex[lang])}
            className="group flex w-full items-center gap-3 rounded-xl border border-border bg-background px-4 py-3 text-left shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/5 dark:hover:bg-primary/10 disabled:opacity-50"
          >
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-primary">
                {lang === 'vi' ? ex.labelVi : ex.labelEn}
              </p>
              <p className="truncate text-xs text-muted-foreground">"{ex[lang]}"</p>
            </div>
            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-border transition-colors group-hover:text-primary" />
          </button>
        ))}
      </div>

      <p className="mt-4 text-xs text-muted-foreground">{t('empty.tip')}</p>
    </div>
  )
}
