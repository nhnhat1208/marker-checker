import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import MarkerLogo from '@/components/brand/MarkerLogo'
import { Input } from '@/components/ui/input'
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
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)

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

  const filteredByCategory = activeCategory === 'all'
    ? examples
    : examples.filter(e => e.category === activeCategory)

  const filtered = filteredByCategory.filter((example) => {
    const haystack = [example.labelEn, example.labelVi, example.en, example.vi, example.categoryLabel].join(' ').toLowerCase()
    return haystack.includes(query.toLowerCase().trim())
  })
  const pageSize = 6
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize)

  useEffect(() => {
    setPage(0)
  }, [activeCategory, query])

  return (
    <div className="mx-auto mt-8 max-w-3xl text-center">
      <MarkerLogo className="mx-auto mb-4 h-14 w-14 drop-shadow-md" title="Marker Checker" />
      <h2 className="mb-1 text-lg font-semibold text-foreground">{t('empty.headline')}</h2>
      <p className="mb-5 text-sm text-muted-foreground">{t('empty.subtitle')}</p>

      <div className="mx-auto mb-3 max-w-md">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('empty.search', 'Search templates')}
            className="h-10 rounded-full border-border/80 bg-background pl-9 text-sm shadow-sm"
          />
        </div>
      </div>

      {/* Category filter */}
      {categories.length > 1 && (
        <div className="mb-4 flex flex-wrap justify-center gap-1.5">
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
      <div className="grid gap-2 text-left sm:grid-cols-2">
        {visible.map((ex, i) => (
          <button
            key={i}
            disabled={!connected}
            onClick={() => onFill(ex[lang])}
            className="group flex min-h-24 w-full items-start gap-3 rounded-2xl border border-border bg-background px-4 py-3 text-left shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/5 dark:hover:bg-primary/10 disabled:opacity-50"
          >
            <div className="min-w-0 flex-1 space-y-1">
              <p className="text-sm font-semibold text-primary line-clamp-2">
                {lang === 'vi' ? ex.labelVi : ex.labelEn}
              </p>
              <p className="font-mono text-[11px] leading-5 text-muted-foreground/80 line-clamp-3">
                {ex[lang]}
              </p>
            </div>
            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-border transition-colors group-hover:text-primary" />
          </button>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border bg-muted/20 px-4 py-8 text-sm text-muted-foreground">
          {t('empty.no_results')}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between rounded-2xl border border-border bg-background px-3 py-2 text-xs text-muted-foreground shadow-sm">
        <button
          type="button"
          disabled={page === 0 || totalPages === 1}
          onClick={() => setPage((prev) => Math.max(0, prev - 1))}
          className="inline-flex items-center gap-1 rounded-full px-2 py-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-30"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          {t('empty.prev', 'Prev')}
        </button>
        <span className="font-medium text-foreground/80">
          {t('empty.page_info', {
            current: page + 1,
            total: totalPages,
            defaultValue: 'Page {{current}} of {{total}}',
          })}
        </span>
        <button
          type="button"
          disabled={page >= totalPages - 1 || totalPages === 1}
          onClick={() => setPage((prev) => Math.min(totalPages - 1, prev + 1))}
          className="inline-flex items-center gap-1 rounded-full px-2 py-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-30"
        >
          {t('empty.next', 'Next')}
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">{t('empty.tip')}</p>
    </div>
  )
}
