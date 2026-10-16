import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import ListIcon from '~icons/fluent-emoji-flat/clipboard'
import StarIcon from '~icons/fluent-emoji-flat/star'
import PlusIcon from '~icons/lucide/plus'

import type { Member } from '../../api/members'
import { useMe } from '../../api/auth'
import {
  type Redemption,
  type Reward,
  rewardData,
  updateReward,
  useRedemptions,
  useRewardsMutation,
  useCancelRedemption,
} from '../../api/rewards'
import { TaskIcon } from '../../components/TaskIcon'
import { Alert, Button, Section, Switch, TextField } from '../../components/ui'
import { errorMessage } from '../../errors'
import { ChildPicker } from './formParts'

interface RewardsSectionProps {
  /** Nur Kinder; Erwachsene bekommen keine Belohnungen. */
  childMembers: Member[]
  rewards: Reward[] | undefined
  error: unknown
  /** Ausgewähltes Kind. */
  member: Member | undefined
  onSelect: (memberId: number) => void
  onEdit: (reward: Reward) => void
  onAdd: (member: Member) => void
  onPickFromPool: (member: Member) => void
  /** Zeitzone der Familie für Datum und Uhrzeit der Einlösungen. */
  timeZone: string
}

/** Belohnungen je Kind und zuletzt eingelöste Belohnungen. */
export function RewardsSection({
  childMembers,
  rewards,
  error,
  member,
  onSelect,
  onEdit,
  onAdd,
  onPickFromPool,
  timeZone,
}: RewardsSectionProps) {
  const { t } = useTranslation()
  const toggleActive = useRewardsMutation((reward: Reward) =>
    updateReward(reward.id, { ...rewardData(reward), active: !reward.active }),
  )

  if (childMembers.length === 0 || !member) {
    return (
      <Section title={t('rewards.section')}>
        <p className="text-lg text-slate-600">{t('rewards.need_children')}</p>
      </Section>
    )
  }

  const own = (rewards ?? [])
    .filter((reward) => reward.member_id === member.id)
    .sort((a, b) => a.cost - b.cost || a.id - b.id)

  return (
    <Section title={t('rewards.section')}>
      {error ? <Alert>{errorMessage(t, error)}</Alert> : null}
      {toggleActive.isError && <Alert>{errorMessage(t, toggleActive.error)}</Alert>}
      <ChildPicker
        label={t('rewards.choose_child')}
        childMembers={childMembers}
        selected={member}
        onSelect={onSelect}
      />

      {rewards && own.length === 0 && (
        <p className="text-lg text-slate-600">{t('rewards.empty', { name: member.name })}</p>
      )}
      {own.length > 0 && (
        <ul className="flex flex-col gap-3">
          {own.map((reward) => (
            <li
              key={reward.id}
              className={`flex flex-wrap items-center justify-end gap-3 rounded-2xl border-2 border-slate-100 p-2 sm:flex-nowrap sm:p-3 ${reward.active ? '' : 'bg-slate-50'}`}
            >
              <button
                type="button"
                onClick={() => onEdit(reward)}
                aria-label={t('rewards.edit_title', { name: reward.name })}
                className="flex min-w-0 flex-1 basis-full items-center gap-4 rounded-xl p-1 text-left sm:basis-auto transition-colors hover:bg-orange-50 focus-visible:outline-4 focus-visible:outline-orange-400 active:bg-orange-100"
              >
                <TaskIcon
                  icon={reward.icon}
                  className={`size-14 ${reward.active ? '' : 'opacity-40'}`}
                />
                <span className="min-w-0 flex-1 text-lg font-bold break-words text-slate-800">
                  {reward.name}
                  {!reward.active && (
                    <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-sm font-bold text-slate-600">
                      {t('tasks.inactive')}
                    </span>
                  )}
                </span>
                <span className="inline-flex shrink-0 items-center gap-1 text-lg font-extrabold text-slate-700">
                  <StarIcon className="size-6" aria-hidden="true" />
                  <span aria-hidden="true">{reward.cost}</span>
                  <span className="sr-only">{t('tasks.points_count', { count: reward.cost })}</span>
                </span>
              </button>
              <Switch
                checked={reward.active}
                onChange={() => toggleActive.mutate(reward)}
                disabled={toggleActive.isPending && toggleActive.variables?.id === reward.id}
                label={t('rewards.active_toggle', { name: reward.name })}
              />
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-3">
        <Button onClick={() => onPickFromPool(member)} disabled={rewards === undefined}>
          <ListIcon className="size-7" aria-hidden="true" />
          {t('rewards.from_pool')}
        </Button>
        <Button variant="secondary" onClick={() => onAdd(member)} disabled={rewards === undefined}>
          <PlusIcon className="size-6" aria-hidden="true" />
          {t('rewards.add_custom')}
        </Button>
      </div>

      <RedemptionHistory member={member} timeZone={timeZone} />
    </Section>
  )
}

export function RedemptionHistory({ member, timeZone }: { member: Member; timeZone: string }) {
  const { t } = useTranslation()
  const history = useRedemptions(member.id)
  const redemptions = history.data?.pages.flatMap((page) => page.redemptions) ?? []

  return (
    <div className="flex flex-col gap-3 border-t-2 border-slate-100 pt-4">
      <h3 className="text-xl font-extrabold text-slate-800">
        {t('rewards.history', { name: member.name })}
      </h3>
      {history.isError && <Alert>{errorMessage(t, history.error)}</Alert>}
      {history.isSuccess && redemptions.length === 0 && (
        <p className="text-lg text-slate-600">{t('rewards.history_empty')}</p>
      )}
      {redemptions.length > 0 && (
        <ul className="flex flex-col divide-y divide-slate-100">
          {redemptions.map((redemption) => (
            <RedemptionRow key={redemption.id} redemption={redemption} timeZone={timeZone} />
          ))}
        </ul>
      )}
      {history.hasNextPage && (
        <Button
          variant="secondary"
          className="self-start"
          disabled={history.isFetchingNextPage}
          onClick={() => void history.fetchNextPage()}
        >
          {t('rewards.load_more')}
        </Button>
      )}
    </div>
  )
}

function RedemptionRow({ redemption, timeZone }: { redemption: Redemption; timeZone: string }) {
  const { t, i18n } = useTranslation()
  const role = useMe().data?.user.role
  const canCancel = role === 'admin' || role === 'parent'
  const cancel = useCancelRedemption()
  const [editing, setEditing] = useState(false)
  const [reason, setReason] = useState('')
  const cancelled = redemption.status === 'cancelled'
  const language = i18n.resolvedLanguage ?? i18n.language
  const when = new Intl.DateTimeFormat(language, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(redemption.created_at))

  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <TaskIcon icon={redemption.reward_icon} className="size-12" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-lg font-bold break-words text-slate-800">
          {redemption.reward_name}
        </span>
        <span className="text-base text-slate-500">{when}</span>
        {cancelled && (
          <span className="text-base text-green-800">
            {t('rewards.cancelled')}{' '}
            {redemption.cancelled_at &&
              new Intl.DateTimeFormat(language, {
                dateStyle: 'medium',
                timeStyle: 'short',
                timeZone,
              }).format(new Date(redemption.cancelled_at))}
            {redemption.cancellation_reason && ` · ${redemption.cancellation_reason}`}
          </span>
        )}
      </span>
      <span
        className={`shrink-0 rounded-full px-3 py-1 text-xl font-extrabold tabular-nums ${cancelled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}
      >
        {cancelled ? t('rewards.refunded', { count: redemption.cost }) : `−${redemption.cost}`}
      </span>
      {canCancel && !cancelled && !editing && (
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {t('rewards.cancel')}
        </Button>
      )}
      {canCancel && !cancelled && editing && (
        <form
          className="flex w-full flex-col gap-3 rounded-xl bg-orange-50 p-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (reason.trim())
              cancel.mutate(
                { id: redemption.id, reason: reason.trim() },
                { onSuccess: () => setEditing(false) },
              )
          }}
        >
          <p>{t('rewards.cancel_hint', { count: redemption.cost })}</p>
          <TextField
            label={t('rewards.cancel_reason')}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            required
            maxLength={200}
          />
          {cancel.isError && <Alert>{errorMessage(t, cancel.error)}</Alert>}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={cancel.isPending || !reason.trim()}>
              {t('rewards.cancel_confirm')}
            </Button>
            <Button
              variant="secondary"
              disabled={cancel.isPending}
              onClick={() => setEditing(false)}
            >
              {t('actions.cancel')}
            </Button>
          </div>
        </form>
      )}
    </li>
  )
}
