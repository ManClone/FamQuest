import { useTranslation } from 'react-i18next'
import ScaleIcon from '~icons/fluent-emoji-flat/balance-scale'

import { Avatar } from '../../components/Avatar'
import { Alert, Button } from '../../components/ui'
import { errorMessage } from '../../errors'
import type { CareSegment } from '../../care'
import { colorTokens } from '../../memberColors'

interface ChoreShareProps {
  /** Anteile aller Beteiligten (siehe careShares). */
  shares: CareSegment[]
  /** So viele Tage zählt die Verteilung zurück. */
  days: number
  /** Kompakt: nur Balken und Avatare mit Prozent, für die Spalte unter „Aufgaben“. */
  compact?: boolean
  onDaysChange?: (days: number) => void
  loading?: boolean
  error?: unknown
  onRetry?: () => void
}

/**
 * Faire Verteilung: wer wie viel vom Putzplan erledigt hat, als geteilter Balken in den
 * Personenfarben. Kein Wettbewerb, sondern ein Blick darauf, wie sich die Arbeit verteilt.
 */
export function ChoreShare({
  shares,
  days,
  compact = false,
  onDaysChange,
  loading,
  error,
  onRetry,
}: ChoreShareProps) {
  const { t } = useTranslation()
  const parents = shares.filter((share) => share.member.role === 'parent')
  const hasTime = parents.some((share) => share.minutes > 0)
  const legend = (share: CareSegment) =>
    share.member.role !== 'parent'
      ? t('care.child_legend', {
          name: share.member.name,
          count: share.count,
          percent: share.taskPercent,
        })
      : t('care.time_legend', {
          name: share.member.name,
          count: share.count,
          percent: share.percent,
          minutes: share.minutes,
        })
  const period = t('care.period', { days })

  const bar = (
    <span
      role="img"
      aria-label={`${t('care.parent_time')} (${period}): ${parents.map(legend).join('; ')}`}
      className={`flex w-full overflow-hidden rounded-full bg-slate-200 shadow-inner ${compact ? 'h-3' : 'h-6'}`}
    >
      {parents.map((share) => (
        <span
          key={share.member.id}
          className="block h-full transition-[width] duration-500 motion-reduce:transition-none"
          style={{
            width: `${share.percent}%`,
            backgroundColor: colorTokens(share.member.color).main,
          }}
        />
      ))}
    </span>
  )

  if (compact) {
    return (
      <div
        className="flex w-full max-w-72 flex-col gap-1"
        role="group"
        aria-label={`${t('care.title')} (${period}): ${shares.map(legend).join('; ')}`}
      >
        {hasTime && bar}
        <ul aria-hidden="true" className="flex flex-wrap justify-center gap-x-3 gap-y-2">
          {shares.map((share) => (
            <li key={share.member.id} className="flex min-w-0 items-center gap-1">
              <Avatar
                name={share.member.name}
                color={share.member.color}
                src={share.member.avatar_url}
                size="xs"
              />
              <span className="text-sm font-extrabold text-slate-700 tabular-nums">
                {t('care.child_count', { count: share.count })} ·{' '}
                {share.member.role === 'parent' && (
                  <>{t('care.minutes', { minutes: share.minutes })} · </>
                )}
                {t('care.percent', {
                  percent: share.member.role === 'parent' ? share.percent : share.taskPercent,
                })}
              </span>
            </li>
          ))}
        </ul>
      </div>
    )
  }
  return (
    <section
      aria-labelledby="chore-share-title"
      className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-sm"
    >
      <h2 id="chore-share-title" className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <ScaleIcon className="size-9 shrink-0" aria-hidden="true" />
        <span className="text-2xl font-extrabold text-slate-800">{t('care.title')}</span>
        {onDaysChange ? (
          <label className="max-w-full text-base font-bold text-slate-600">
            <span className="sr-only">{t('care.range')}</span>
            <select
              value={days}
              onChange={(event) => onDaysChange(Number(event.target.value))}
              className="min-h-11 max-w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-700 focus-visible:outline-2 focus-visible:outline-orange-400"
            >
              <option value={7}>{t('care.days_7')}</option>
              <option value={30}>{t('care.days_30')}</option>
              <option value={365}>{t('care.year')}</option>
            </select>
          </label>
        ) : (
          <span className="text-lg font-bold text-slate-500">{period}</span>
        )}
      </h2>
      {loading ? (
        <p role="status">{t('common.loading')}</p>
      ) : error ? (
        <div className="flex flex-col gap-2">
          <Alert>{errorMessage(t, error)}</Alert>
          {onRetry && (
            <Button variant="secondary" onClick={onRetry}>
              {t('actions.retry')}
            </Button>
          )}
        </div>
      ) : shares.length === 0 ? (
        <p className="text-slate-600">{t('care.empty')}</p>
      ) : (
        <>
          {hasTime && (
            <p className="text-sm font-semibold text-slate-600">{t('care.parent_time')}</p>
          )}
          {hasTime && bar}
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            {shares.map((share) => (
              <li key={share.member.id} className="flex items-center gap-2">
                <Avatar
                  name={share.member.name}
                  color={share.member.color}
                  src={share.member.avatar_url}
                  size="sm"
                />
                <span className="sr-only">{legend(share)}</span>
                <span aria-hidden="true" className="flex flex-col leading-tight">
                  <span className="text-lg font-extrabold text-slate-800">{share.member.name}</span>
                  <span className="text-base font-bold text-slate-600 tabular-nums">
                    {t('care.child_count', { count: share.count })} ·{' '}
                    {share.member.role === 'parent' && (
                      <>{t('care.minutes', { minutes: share.minutes })} · </>
                    )}
                    {t('care.percent', {
                      percent: share.member.role === 'parent' ? share.percent : share.taskPercent,
                    })}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-sm text-slate-500">{t('care.percent_basis')}</p>
          {hasTime && <p className="text-sm text-slate-500">{t('care.time_basis')}</p>}
        </>
      )}
    </section>
  )
}
