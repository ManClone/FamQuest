import { useTranslation } from 'react-i18next'
import StarIcon from '~icons/fluent-emoji-flat/star'
import GiftIcon from '~icons/fluent-emoji-flat/wrapped-gift'

import type { Member } from '../../api/members'
import type { Reward } from '../../api/rewards'
import { TaskIcon } from '../../components/TaskIcon'
import { colorTokens } from '../../memberColors'

interface RewardCardProps {
  compact?: boolean
  canRedeem?: boolean
  reward: Reward
  member: Member
  /** Aktueller Punktestand des Kindes. */
  balance: number
  onRedeem: () => void
}

/** Große Belohnungskarte: mit genug Punkten „Einlösen“, sonst wie viele noch fehlen. */
export function RewardCard({
  reward,
  member,
  balance,
  onRedeem,
  compact = false,
  canRedeem = true,
}: RewardCardProps) {
  const { t } = useTranslation()
  const tokens = colorTokens(member.color)
  const missing = reward.cost - balance
  const affordable = missing <= 0

  return (
    <li
      className={`flex min-w-0 flex-col items-center ${compact ? 'gap-2 rounded-2xl p-3' : 'gap-3 rounded-3xl p-4'} border-4 bg-white text-center shadow-sm`}
      style={{ borderColor: affordable ? tokens.main : 'transparent' }}
    >
      <TaskIcon icon={reward.icon} className={compact ? 'size-14' : 'size-24'} />
      <h3
        className={`${compact ? 'text-lg leading-snug' : 'text-2xl'} font-extrabold break-words hyphens-auto text-slate-800`}
      >
        {reward.name}
      </h3>
      <p
        className={`flex items-center gap-1 ${compact ? 'text-lg' : 'text-2xl'} font-extrabold text-slate-700`}
      >
        <StarIcon className={compact ? 'size-5' : 'size-8'} aria-hidden="true" />
        <span aria-hidden="true">{reward.cost}</span>
        <span className="sr-only">{t('tasks.points_count', { count: reward.cost })}</span>
      </p>
      {affordable || !canRedeem ? (
        <button
          type="button"
          onClick={onRedeem}
          disabled={!canRedeem}
          aria-label={t('rewards.redeem_label', { name: reward.name })}
          className={`mt-auto flex w-full items-center justify-center ${compact ? 'min-h-12 gap-2 rounded-xl px-2 py-2 text-base' : 'min-h-20 gap-3 rounded-2xl px-4 text-2xl'} font-extrabold shadow-sm disabled:opacity-50 disabled:cursor-not-allowed transition-transform focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-orange-400 active:scale-95 motion-reduce:transition-none motion-reduce:active:scale-100`}
          style={{ backgroundColor: tokens.main, color: tokens.onMain }}
        >
          <GiftIcon className={compact ? 'size-6' : 'size-10'} aria-hidden="true" />
          {t('rewards.redeem')}
        </button>
      ) : (
        <div className="mt-auto flex w-full flex-col items-center gap-2">
          <span
            role="img"
            aria-label={t('rewards.progress', { balance, cost: reward.cost })}
            className={`block ${compact ? 'h-3' : 'h-5'} w-full overflow-hidden rounded-full bg-slate-100 shadow-inner`}
          >
            <span
              className="block h-full rounded-full"
              style={{
                width: `${Math.max(0, (balance / reward.cost) * 100)}%`,
                backgroundColor: tokens.main,
              }}
            />
          </span>
          <span
            className={`${compact ? 'text-sm' : 'text-lg'} font-bold text-balance text-slate-600`}
          >
            {t('rewards.missing', { count: missing })}
          </span>
        </div>
      )}
    </li>
  )
}
