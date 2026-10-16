import { useTranslation } from 'react-i18next'
import StarIcon from '~icons/fluent-emoji-flat/star'
import type { Member } from '../../api/members'
import { useMemberProgress } from '../../api/points'

function PraiseCount({ memberId }: { memberId: number }) {
  const { t } = useTranslation()
  const progress = useMemberProgress(memberId)
  const count = progress.data?.praise_count
  return (
    <span
      className="flex items-center gap-1.5"
      aria-label={count === undefined ? t('common.loading') : t('praise.count', { count })}
    >
      <span aria-hidden="true">❤️</span>
      <span aria-hidden="true">{count ?? '–'}</span>
    </span>
  )
}

export function RewardSummary({ member, total }: { member: Member; total: number }) {
  const { t } = useTranslation()
  return (
    <span className="flex shrink-0 items-center gap-3 text-sm font-extrabold tabular-nums">
      <span
        className="flex items-center gap-1.5"
        aria-label={t('child_progress.stars', { count: total })}
      >
        <StarIcon className="size-5" aria-hidden="true" />
        <span aria-hidden="true">{total}</span>
      </span>
      {member.role === 'child' && <PraiseCount memberId={member.id} />}
    </span>
  )
}
