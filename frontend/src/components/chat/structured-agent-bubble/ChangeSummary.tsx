import { useTranslation } from 'react-i18next'

type Props = {
  from?: string
  to?: string
  fromLabel?: string
  toLabel?: string
}

export default function ChangeSummary({ from, to, fromLabel, toLabel }: Props) {
  const { t } = useTranslation()
  const resolvedFromLabel = fromLabel ?? t('change_summary.current', 'Current state')
  const resolvedToLabel = toLabel ?? t('change_summary.proposed', 'Proposed state')

  if (!from && !to) return null

  return (
    <div className="grid gap-2 text-xs sm:grid-cols-2">
      {from && (
        <div className="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-400">
          <span className="font-medium">{resolvedFromLabel}: </span>
          {from}
        </div>
      )}
      {to && (
        <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-400">
          <span className="font-medium">{resolvedToLabel}: </span>
          {to}
        </div>
      )}
    </div>
  )
}
