import { useTranslation } from 'react-i18next'

type Props = {
  note: string
}

export default function ImpactNoteSummary({ note }: Props) {
  const { t } = useTranslation()
  if (!note.trim()) return null

  return (
    <div className="rounded-lg border border-primary/15 bg-primary/5 px-3 py-2.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary/80">
        {t('chat_card.impact_note', 'LLM note')}
      </span>
      <p className="mt-1.5 text-xs leading-6 text-foreground/80">
        {note}
      </p>
    </div>
  )
}
