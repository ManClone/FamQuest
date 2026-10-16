import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import GiftIcon from '~icons/fluent-emoji-flat/wrapped-gift'
import StarIcon from '~icons/fluent-emoji-flat/star'
import { useMe } from '../api/auth'
import { pointsFor } from '../api/today'
import { Alert, Button, Section } from '../components/ui'
import { errorMessage } from '../errors'
import { useFamilyToday } from './family/useFamilyToday'
import { ChildPicker } from './parents/formParts'
import { RedemptionHistory } from './parents/RewardsSection'
import { RewardGrid } from './rewards/RewardGrid'

/** Everyday parent board, independent of reward administration in Settings. */
export function RewardsBoardPage() {
  const { t } = useTranslation()
  const me = useMe().data
  const family = useFamilyToday()
  const [selected, setSelected] = useState<number | null>(null)
  const children = family.members ?? []
  const member =
    children.find((child) => child.id === selected) ??
    children.find((person) => person.id === me?.member_id) ??
    children[0]
  const total = member && family.today ? pointsFor(family.today, member.id).total : 0
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <header className="flex flex-wrap items-center gap-3">
        <GiftIcon className="size-12" aria-hidden="true" />
        <h1 className="text-3xl font-extrabold text-orange-600">{t('rewards.title')}</h1>
        {member && (
          <p className="ml-auto flex items-center gap-2 rounded-2xl bg-white px-4 py-2 text-2xl font-extrabold text-slate-800 shadow-sm">
            <StarIcon className="size-9" aria-hidden="true" />
            {t('points.total_label', { count: total })}
          </p>
        )}
      </header>
      {family.isPending ? (
        <p role="status">{t('common.loading')}</p>
      ) : family.error ? (
        <>
          <Alert>{errorMessage(t, family.error)}</Alert>
          <Button onClick={() => void family.refetch()}>{t('actions.retry')}</Button>
        </>
      ) : !member ? (
        <p>{t('rewards.need_parents')}</p>
      ) : (
        <>
          <ChildPicker
            label={t('rewards.choose_member')}
            childMembers={children}
            selected={member}
            onSelect={setSelected}
          />
          {member.id !== me?.member_id && (
            <p className="rounded-2xl bg-white p-3 text-slate-600">{t('rewards.own_only')}</p>
          )}
          <RewardGrid member={member} balance={total} canRedeem={member.id === me?.member_id} />
          <Section title={t('child_progress.reward_history')}>
            <RedemptionHistory
              member={member}
              timeZone={me?.family.timezone ?? 'Europe/Berlin'}
              readOnly={member.id !== me?.member_id}
            />
          </Section>
        </>
      )}
    </main>
  )
}
