import { type FormEvent, useEffect, useId, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { api, apiGet } from '../../api/client'
import { useParentMutation } from '../../api/mutations'
import { POINTS_KEY, PROGRESS_KEY } from '../../api/points'
import { TODAY_KEY } from '../../api/today'
import { Alert, Button, Section, TextField } from '../../components/ui'
import { errorMessage } from '../../errors'
import { newRequestKey } from '../../request-key'

type Level = 'conversation' | 'light' | 'heavy' | 'severe'
type Context = {
  date: string
  week_start: string
  allowance_cents: number
  earned_bonus_cents: number
  money_penalty_cents: number
  payable_bonus_cents: number
  total_cents: number
  closed: boolean
  requires_review: boolean
  spendable_stars: number
  levels: Record<Level, { stars: number; bonus_cents: number }>
}
type Entry = {
  id: number
  title: string
  effective_date: string
  money_penalty_cents: number
  xp_penalty_applied: number
  reversed: boolean
  reversal_note: string | null
}
const KEY = ['criticism'] as const

export function CriticismPanel({
  memberId,
  mode = 'all',
}: {
  memberId: number
  mode?: 'all' | 'money' | 'criticism'
}) {
  const { t, i18n } = useTranslation()
  const descriptionId = useId()
  const [severity, setSeverity] = useState<Level>('conversation')
  const [money, setMoney] = useState(false)
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [paidConfirmed, setPaidConfirmed] = useState(false)
  const [notice, setNotice] = useState(false)
  const [requestKey, setRequestKey] = useState(newRequestKey)
  const [reversing, setReversing] = useState<number | null>(null)
  const [correction, setCorrection] = useState('')
  const [reversalConfirmed, setReversalConfirmed] = useState(false)
  const state = useQuery({
    queryKey: [...KEY, memberId],
    queryFn: () => apiGet<Context>(`/members/${memberId}/criticism`),
  })
  const invalidates = [KEY, POINTS_KEY, TODAY_KEY, PROGRESS_KEY, ['money']]
  const history = useQuery({
    queryKey: [...KEY, memberId, 'history'],
    queryFn: () => apiGet<Entry[]>(`/members/${memberId}/consequences`),
  })
  const reverse = useParentMutation(
    (body: { id: number; reason: string }) =>
      api('POST', `/consequences/${body.id}/reverse`, {
        confirmed: true,
        reason: body.reason,
      }),
    invalidates,
  )
  const save = useParentMutation((body: object) => api('POST', '/consequences', body), invalidates)
  const close = useParentMutation(
    (body: object) => api('POST', `/members/${memberId}/weekly-bonus/close`, body),
    [KEY],
  )
  const euro = (cents: number) =>
    new Intl.NumberFormat(i18n.language, {
      style: 'currency',
      currency: 'EUR',
    }).format(cents / 100)
  const data = state.data
  useEffect(() => {
    setConfirmed(false)
    setPaidConfirmed(false)
  }, [data?.total_cents, data?.payable_bonus_cents, data?.spendable_stars, data?.closed])
  const level = data?.levels[severity]
  const mayDeductMoney =
    !!data &&
    !!level &&
    level.bonus_cents > 0 &&
    !data.closed &&
    data.payable_bonus_cents > level.bonus_cents
  const deduct = money && mayDeductMoney ? level!.bonus_cents : 0
  const stars = Math.min(level?.stars ?? 0, data?.spendable_stars ?? 0)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!data || !confirmed || !reason.trim()) return
    save.mutate(
      {
        member_id: memberId,
        severity,
        title: reason.trim(),
        apply_money: deduct > 0,
        confirmed: true,
        request_key: requestKey,
        expected_bonus_cents: data.payable_bonus_cents,
      },
      {
        onSuccess: () => {
          setReason('')
          setConfirmed(false)
          setMoney(false)
          setNotice(true)
          setRequestKey(newRequestKey())
        },
      },
    )
  }
  return (
    <Section title={t(mode === 'money' ? 'family_account.week' : 'family_account.criticism')}>
      {state.isPending && <p role="status">{t('common.loading')}</p>}
      {state.isError && <Alert>{errorMessage(t, state.error)}</Alert>}
      {data && (
        <>
          {mode !== 'criticism' && (
            <>
              <p>{t('criticism.protection')}</p>
              <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 break-words">
                <dt>{t('criticism.allowance')}</dt>
                <dd>{euro(data.allowance_cents)}</dd>
                <dt>{t('criticism.earned')}</dt>
                <dd>{euro(data.earned_bonus_cents)}</dd>
                <dt>{t('criticism.deductions')}</dt>
                <dd>{euro(data.money_penalty_cents)}</dd>
                <dt>{t('criticism.remaining')}</dt>
                <dd>{euro(data.payable_bonus_cents)}</dd>
                <dt>{t('criticism.total')}</dt>
                <dd>{euro(data.total_cents)}</dd>
              </dl>
            </>
          )}
          {data.closed && <p>{t('criticism.closed')}</p>}
          {data.requires_review && <Alert>{t('criticism.review')}</Alert>}
          {mode !== 'money' && (
            <form onSubmit={submit} className="flex min-w-0 flex-col gap-4">
              <label className="flex min-w-0 flex-col gap-2 font-bold">
                {t('criticism.level')}
                <select
                  className="min-h-12 w-full min-w-0 max-w-full rounded-lg border p-2"
                  aria-describedby={descriptionId}
                  value={severity}
                  onChange={(event) => {
                    setSeverity(event.target.value as Level)
                    setMoney(false)
                    setConfirmed(false)
                  }}
                >
                  {(['conversation', 'light', 'heavy', 'severe'] as const).map((value) => (
                    <option key={value} value={value}>
                      {t(`family_account.levels.${value}`)}
                    </option>
                  ))}
                </select>
              </label>
              <p id={descriptionId} className="break-words text-sm text-slate-600">
                {t(`criticism.${severity}`)}
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={money && mayDeductMoney}
                  disabled={!mayDeductMoney}
                  onChange={(event) => {
                    setMoney(event.target.checked)
                    setConfirmed(false)
                  }}
                />{' '}
                {t('criticism.optional_money', { amount: euro(level?.bonus_cents ?? 0) })}
              </label>
              <TextField
                label={t('criticism.reason')}
                value={reason}
                maxLength={100}
                onChange={(event) => {
                  setReason(event.target.value)
                  setConfirmed(false)
                }}
                required
              />
              <p>
                {t('criticism.preview', {
                  stars,
                  amount: euro(deduct),
                  remaining: euro(data.payable_bonus_cents - deduct),
                })}
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />{' '}
                {t('criticism.confirm')}
              </label>
              {save.isError && <Alert>{errorMessage(t, save.error)}</Alert>}
              {notice && <p role="status">{t('criticism.saved')}</p>}
              <Button type="submit" disabled={save.isPending || !confirmed || !reason.trim()}>
                {t('criticism.save')}
              </Button>
            </form>
          )}
          {mode !== 'criticism' && !data.closed && (
            <div className="mt-6 flex flex-col gap-3 border-t pt-4">
              <p>{t('criticism.close_hint')}</p>
              <label>
                <input
                  type="checkbox"
                  checked={paidConfirmed}
                  onChange={(event) => setPaidConfirmed(event.target.checked)}
                />{' '}
                {t('criticism.paid_confirm', { amount: euro(data.total_cents) })}
              </label>
              {close.isError && <Alert>{errorMessage(t, close.error)}</Alert>}
              <Button
                variant="secondary"
                disabled={!paidConfirmed || close.isPending}
                onClick={() =>
                  close.mutate(
                    { date: data.date, confirmed: true, expected_total_cents: data.total_cents },
                    {
                      onSuccess: () => setPaidConfirmed(false),
                    },
                  )
                }
              >
                {t('criticism.close')}
              </Button>
            </div>
          )}
          {mode !== 'money' && (
            <details className="mt-6 border-t pt-4">
              <summary className="cursor-pointer font-bold">{t('criticism.history')}</summary>
              {history.isError && <Alert>{errorMessage(t, history.error)}</Alert>}
              <ul className="flex flex-col gap-4 pt-3">
                {history.data?.map((entry) => (
                  <li key={entry.id}>
                    <p>
                      {entry.effective_date} · {entry.title}
                    </p>
                    <p>
                      {t('criticism.record', {
                        stars: entry.xp_penalty_applied,
                        amount: euro(entry.money_penalty_cents),
                      })}
                    </p>
                    {entry.reversed ? (
                      <p>
                        {t('criticism.reversed')} · {entry.reversal_note}
                      </p>
                    ) : (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setReversing(entry.id)
                          setCorrection('')
                          setReversalConfirmed(false)
                        }}
                      >
                        {t('criticism.reverse')}
                      </Button>
                    )}
                    {reversing === entry.id && !entry.reversed && (
                      <div className="flex flex-col gap-3 pt-2">
                        <TextField
                          label={t('criticism.correction_reason')}
                          value={correction}
                          maxLength={500}
                          onChange={(event) => {
                            setCorrection(event.target.value)
                            setReversalConfirmed(false)
                          }}
                        />
                        <label>
                          <input
                            type="checkbox"
                            checked={reversalConfirmed}
                            onChange={(event) => setReversalConfirmed(event.target.checked)}
                          />{' '}
                          {t('criticism.reverse_confirm')}
                        </label>
                        {reverse.isError && <Alert>{errorMessage(t, reverse.error)}</Alert>}
                        <Button
                          disabled={!reversalConfirmed || !correction.trim() || reverse.isPending}
                          onClick={() =>
                            reverse.mutate(
                              { id: entry.id, reason: correction.trim() },
                              {
                                onSuccess: () => setReversing(null),
                              },
                            )
                          }
                        >
                          {t('criticism.reverse_save')}
                        </Button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </Section>
  )
}
