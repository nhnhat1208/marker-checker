import type { TFunction } from 'i18next'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTranslation } from 'react-i18next'
import type { UiDraftSummary } from '@/lib/chatTypes'

type Props = {
  missingFields?: string[] | null
  draft?: UiDraftSummary | null
  onFieldClick?: (text: string) => void
  hiddenAction?: boolean
}

const ORDERED_FIELDS = [
  'target_label',
  'change_from_summary',
  'change_to_summary',
  'approver_handle',
] as const

function labelForField(field: string, t: TFunction) {
  return t(`missing_info.fields.${field}`, field.replace(/_/g, ' '))
}

function joinLabels(labels: string[], lang: 'en' | 'vi') {
  if (labels.length <= 1) return labels[0] ?? ''
  if (labels.length === 2) return lang === 'vi' ? `${labels[0]} và ${labels[1]}` : `${labels[0]} and ${labels[1]}`
  const head = labels.slice(0, -1).join(', ')
  const tail = labels[labels.length - 1]
  return lang === 'vi' ? `${head} và ${tail}` : `${head}, and ${tail}`
}

function buildFillPrompt(
  fields: string[],
  draft: UiDraftSummary | null | undefined,
  t: TFunction,
) {
  const knownValues: Record<string, string> = {
    target_label: draft?.target_label?.trim() ?? '',
    change_from_summary: draft?.change_from_summary?.trim() ?? '',
    change_to_summary: draft?.change_to_summary?.trim() ?? '',
    approver_handle: draft?.approver_handle?.trim() ?? '',
  }

  const visibleFields = ORDERED_FIELDS.filter((field) => fields.includes(field) || knownValues[field])

  return visibleFields
    .map((field) => `${labelForField(field, t)}: ${knownValues[field] || '...'}`)
    .join('\n')
}

function FieldStatus({
  label,
  value,
  missing,
  placeholder,
}: {
  label: string
  value?: string
  missing?: boolean
  placeholder: string
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-muted/40 px-3 py-2 text-xs">
      <div className="flex items-center gap-2 text-muted-foreground">
        {missing ? (
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
        )}
        <span>{label}</span>
      </div>
      <div className={missing ? 'mt-1 font-medium text-rose-600 dark:text-rose-400' : 'mt-1 font-medium text-foreground'}>
        {value || placeholder}
      </div>
    </div>
  )
}

export default function MissingFieldsCallout({ missingFields, draft, onFieldClick, hiddenAction = false }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('vi') ? 'vi' : 'en'
  const fields = (missingFields ?? []).filter(Boolean)

  if (fields.length === 0) return null

  const knownValues: Record<string, string> = {
    target_label: draft?.target_label?.trim() ?? '',
    change_from_summary: draft?.change_from_summary?.trim() ?? '',
    change_to_summary: draft?.change_to_summary?.trim() ?? '',
    approver_handle: draft?.approver_handle?.trim() ?? '',
  }
  const fieldLabels = fields.map((field) => labelForField(field, t))
  const joinedFields = joinLabels(fieldLabels, lang)
  const fillPrompt = buildFillPrompt(fields, draft, t)
  const placeholder = t('missing_info.placeholder', 'Not provided yet')
  const targetMissing = fields.includes('target_label')
  const fromMissing = fields.includes('change_from_summary')
  const toMissing = fields.includes('change_to_summary')
  const approverMissing = fields.includes('approver_handle')

  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-background shadow-md">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/70 bg-primary/5 px-4 py-2.5">
        <span className="rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
          {t('chat_card.draft_badge', 'Draft')}
        </span>
        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
          {t('chat_card.needs_details_badge', 'Needs details')}
        </span>
      </div>

      <div className="space-y-3 p-4">
        <p className="text-sm leading-6 text-foreground/80">
          {t('missing_info.guidance', 'I still need {{fields}} before I can continue.', {
            fields: joinedFields,
          })}
        </p>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          {draft?.requester_handle && (
            <span>
              {t('chat_card.meta_requester', 'Requester')}: <span className="font-medium text-foreground">{draft.requester_handle}</span>
            </span>
          )}
          <span>
            {t('chat_card.meta_approver', 'Approver')}:{' '}
            <span className={approverMissing ? 'font-medium text-rose-600 dark:text-rose-400' : 'font-medium text-foreground'}>
              {knownValues.approver_handle || placeholder}
            </span>
          </span>
          <span>
            {t('chat_card.meta_target', 'Target')}:{' '}
            <span className={targetMissing ? 'font-mono font-medium text-rose-600 dark:text-rose-400' : 'font-mono font-medium text-foreground'}>
              {knownValues.target_label || placeholder}
            </span>
          </span>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <FieldStatus
            label={t('change_summary.current', 'Current state')}
            value={knownValues.change_from_summary}
            missing={fromMissing}
            placeholder={placeholder}
          />
          <FieldStatus
            label={t('change_summary.proposed', 'Proposed state')}
            value={knownValues.change_to_summary}
            missing={toMissing}
            placeholder={placeholder}
          />
        </div>

        {!hiddenAction && (
          <div className="flex justify-start border-t border-border/70 pt-3">
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={() => onFieldClick?.(fillPrompt)}
              className="h-8 rounded-full bg-emerald-600 px-3 text-xs font-medium text-white shadow-sm hover:bg-emerald-500 dark:bg-emerald-500 dark:hover:bg-emerald-400"
            >
              {t('missing_info.action')}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
