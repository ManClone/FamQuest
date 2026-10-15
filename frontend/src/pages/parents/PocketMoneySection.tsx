import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  useAllowancePaymentStatus,
  useBankBalances,
  useBankTransactions,
  useMoneyOverview,
  useWeeklyAllowanceSettings,
  useSaveWeeklyAllowanceSettings,
} from '../../api/money'
import type { Member } from '../../api/members'
import { Alert, Button, Section } from '../../components/ui'
import { errorMessage } from '../../errors'

export function PocketMoneySection({ children }: { children: Member[] }) {
  const { t, i18n } = useTranslation()
  const [memberId, setMemberId] = useState<number | null>(null)
  const selected = children.find((child) => child.id === memberId) ?? children[0]
  const id = selected?.id ?? 0
  const overview = useMoneyOverview(id)
  const status = useAllowancePaymentStatus(id)
  const bankBalances = useBankBalances(id)
  const bankTransactions = useBankTransactions(id)
  const settings = useWeeklyAllowanceSettings(id)
  const saveSettings = useSaveWeeklyAllowanceSettings(id)
  const [weeklyAmount, setWeeklyAmount] = useState('')
  const [message, setMessage] = useState('')
  const euros = (cents: number) =>
    new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'EUR' }).format(cents / 100)

  return (
    <Section title={t('pocket_money.title')}>
      {!selected ? (
        <p>{t('pocket_money.no_child')}</p>
      ) : (
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 font-bold">
            {t('pocket_money.child')}
            <select
              value={selected.id}
              onChange={(event) => {
                setMemberId(Number(event.target.value))
                setWeeklyAmount('')
                setMessage('')
              }}
              className="min-h-12 rounded-xl border-2 border-slate-200 bg-white p-2"
            >
              {children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.name}
                </option>
              ))}
            </select>
          </label>
          {overview.isError && <Alert>{errorMessage(t, overview.error)}</Alert>}
          {overview.data && (
            <dl className="grid grid-cols-2 gap-3">
              <div>
                <dt>{t('pocket_money.title')}</dt>
                <dd className="font-bold">{euros(overview.data.allowance_cents)}</dd>
              </div>
              <div>
                <dt>{t('pocket_money.bonus')}</dt>
                <dd className="font-bold">{euros(overview.data.bonus_cents)}</dd>
              </div>
            </dl>
          )}
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              const normalized = weeklyAmount.trim().replace(',', '.')
              const cents = Math.round(Number(normalized) * 100)
              if (!/^\d{1,4}(?:\.\d{1,2})?$/.test(normalized) || cents < 1 || cents > 100000) {
                setMessage(t('pocket_money.invalid_amount'))
                return
              }
              saveSettings.mutate(cents, {
                onSuccess: () => {
                  setWeeklyAmount('')
                  setMessage(t('pocket_money.saved'))
                },
              })
            }}
          >
            <h3 className="font-bold">{t('pocket_money.automatic')}</h3>
            {settings.isError && <Alert>{errorMessage(t, settings.error)}</Alert>}
            <p>
              {t('pocket_money.current')}:{' '}
              {settings.isPending
                ? t('common.loading')
                : settings.data?.weekly_amount_cents == null
                  ? t('pocket_money.not_configured')
                  : euros(settings.data.weekly_amount_cents)}
            </p>
            <p className="text-sm text-slate-500">{t('pocket_money.schedule_hint')}</p>
            <label className="flex flex-col gap-1">
              {t('pocket_money.weekly_amount')}
              <input
                required
                inputMode="decimal"
                value={weeklyAmount}
                onChange={(event) => setWeeklyAmount(event.target.value)}
                className="min-h-12 rounded-xl border-2 border-slate-200 p-2"
              />
            </label>
            {saveSettings.isError && <Alert>{errorMessage(t, saveSettings.error)}</Alert>}
            <Button type="submit" disabled={saveSettings.isPending}>
              {t('pocket_money.save')}
            </Button>
            {settings.data?.weekly_amount_cents != null && (
              <Button
                type="button"
                variant="secondary"
                disabled={saveSettings.isPending}
                onClick={() =>
                  saveSettings.mutate(null, {
                    onSuccess: () => setMessage(t('pocket_money.disabled')),
                  })
                }
              >
                {t('pocket_money.disable')}
              </Button>
            )}
          </form>
          {message && <p role="status">{message}</p>}
          <div className="flex flex-col gap-2 rounded-xl bg-orange-50 p-3">
            <h3 className="font-bold">{t('pocket_money.payment_status')}</h3>
            {status.isError && <Alert>{errorMessage(t, status.error)}</Alert>}
            {status.data && (
              <>
                <p>
                  {t('pocket_money.expected')}: {euros(status.data.expected_cents)}
                </p>
                <p>
                  {t('pocket_money.received')}: {euros(status.data.received_cents)}
                </p>
                <p>
                  {t(
                    status.data.expected_cents === 0
                      ? 'pocket_money.not_due'
                      : status.data.bank_connected
                        ? status.data.missing_cents > 0
                          ? 'pocket_money.missing'
                          : 'pocket_money.confirmed'
                        : 'pocket_money.no_bank',
                    { amount: euros(status.data.missing_cents) },
                  )}
                </p>
              </>
            )}
            <p className="text-sm text-slate-500">{t('pocket_money.bank_hint')}</p>
          </div>
          {bankBalances.data?.map((account) => (
            <p key={account.account_id}>
              {account.display_name}:{' '}
              <strong>
                {account.balance_cents === null
                  ? t('pocket_money.no_balance')
                  : euros(account.balance_cents)}
              </strong>
            </p>
          ))}
          {bankTransactions.data && bankTransactions.data.length > 0 && (
            <div>
              <h3 className="font-bold">{t('pocket_money.transactions')}</h3>
              {bankTransactions.data.map((entry) => (
                <div key={entry.id} className="flex justify-between gap-2 border-b py-2">
                  <span>
                    {entry.booked_on} {entry.description || entry.counterparty}
                  </span>
                  <strong>{euros(entry.amount_cents)}</strong>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Section>
  )
}
