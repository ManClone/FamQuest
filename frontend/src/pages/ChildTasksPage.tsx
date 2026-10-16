import { PraiseCelebration } from '../components/PraiseCelebration'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import StarIcon from '~icons/fluent-emoji-flat/star'
import TrophyIcon from '~icons/fluent-emoji-flat/trophy'
import { useMe } from '../api/auth'
import { useMemberProgress } from '../api/points'
import { daysUntilDue, pointsFor } from '../api/today'
import { Avatar } from '../components/Avatar'
import { Alert } from '../components/ui'
import { errorMessage } from '../errors'
import { colorTokens } from '../memberColors'
import { ViewToggle } from './family/ViewToggle'
import { DayProgress } from './family/DayProgress'
import { TaskGroups } from './family/TaskGroups'
import { currentTasks, tasksFor, useFamilyToday } from './family/useFamilyToday'
import { ChildHouseholdTasks } from './ChildHouseholdTasks'
import { TasksWeekPage } from './TasksWeekPage'

export function ChildTasksPage({ currentOnly = false }: { currentOnly?: boolean }) {
  const { t } = useTranslation()
  const me = useMe().data
  const week = useLocation().pathname === '/tasks/week'
  const { members, today, isPending, error } = useFamilyToday()
  const member = members?.find((person) => person.id === me?.member_id)
  if (isPending)
    return (
      <p role="status" className="p-6">
        {t('common.loading')}
      </p>
    )
  if (!member || !today)
    return (
      <main className="p-6">
        <p>{t('personal.not_linked')}</p>
        <Link to="/settings">{t('nav.settings')}</Link>
        {error && <Alert>{errorMessage(t, error)}</Alert>}
      </main>
    )
  const all = tasksFor(today.tasks, member.id)
  const tasks = all.filter(
    (task) =>
      !currentOnly ||
      task.time_of_day === today.time_of_day ||
      task.time_of_day === null ||
      task.extra ||
      (daysUntilDue(task, member.id, today.date) ?? 0) < 0,
  )
  const points = pointsFor(today, member.id)
  return (
    <main className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
      {currentOnly && <h1 className="text-3xl font-extrabold text-orange-600">{t('nav.today')}</h1>}
      <ChildProgressHeader member={member} total={points.total} currentOnly={currentOnly} />
      <div className="rounded-3xl bg-white/80 p-4 shadow-sm">
        <p className="mb-3 text-center text-lg font-bold text-slate-700">
          {t('child_progress.today_progress')} · {t('points.today_label', { count: points.today })}
        </p>
        <DayProgress
          showPoints={false}
          member={member}
          tasks={currentTasks(all, member.id, today.date)}
          points={points}
          size="lg"
        />
      </div>
      {!currentOnly && <ViewToggle current={week ? 'week' : 'day'} />}
      {week && !currentOnly ? (
        <TasksWeekPage embedded />
      ) : (
        <TaskGroups
          member={member}
          tasks={tasks}
          date={today.date}
          currentTimeOfDay={today.time_of_day}
          size="compact"
        />
      )}
      <ChildHouseholdTasks currentOnly={currentOnly} />
    </main>
  )
}

function ChildProgressHeader({
  member,
  total,
  currentOnly,
}: {
  member: import('../api/members').Member
  total: number
  currentOnly: boolean
}) {
  const { t } = useTranslation()
  const progress = useMemberProgress(member.id)
  const data = progress.data
  const tokens = colorTokens(member.color)
  const Heading = currentOnly ? 'h2' : 'h1'
  return (
    <section
      aria-label={t('child_progress.overview')}
      className="flex flex-col gap-5 rounded-3xl border-2 bg-white p-5 shadow-sm sm:p-6"
      style={{ borderColor: tokens.main }}
    >
      <header className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
        <Avatar name={member.name} color={member.color} src={member.avatar_url} size="lg" />
        <div className="min-w-0 flex-1">
          <Heading className="text-4xl font-extrabold text-slate-800">{member.name}</Heading>
          <p className="text-lg font-bold text-slate-500">{t('child_progress.adventure')}</p>
        </div>
        <div className="col-span-2 flex flex-wrap items-center gap-2 sm:col-span-1">
          <p
            aria-label={t('child_progress.stars', { count: total })}
            className="flex items-center gap-2 rounded-2xl bg-amber-50 px-3 py-2 text-2xl font-extrabold text-slate-800"
          >
            <StarIcon className="size-10" aria-hidden="true" />
            {total}
          </p>
          <p
            aria-label={t('praise.count', { count: data?.praise_count ?? 0 })}
            className="flex items-center gap-2 rounded-2xl bg-rose-50 px-3 py-2 text-2xl font-extrabold text-slate-800"
          >
            <span aria-hidden="true">❤️</span>
            {data?.praise_count ?? 0}
          </p>
        </div>
      </header>
      {data && (
        <PraiseCelebration
          memberId={member.id}
          latestId={data.latest_praise_id ?? 0}
          reason={data.latest_praise_reason}
        />
      )}
      {data ? (
        <div
          className="flex flex-col gap-3 rounded-2xl p-4"
          style={{ backgroundColor: tokens.soft }}
        >
          <div className="flex flex-wrap items-center justify-between gap-2 font-extrabold text-slate-800">
            <p className="flex items-center gap-2 text-2xl">
              <TrophyIcon className="size-9" aria-hidden="true" />
              {t('child_progress.level', { level: data.level })}
            </p>
            <p>
              {t('child_progress.remaining', { count: data.remaining_xp, level: data.level + 1 })}
            </p>
          </div>
          <div
            role="progressbar"
            aria-label={t('child_progress.level_progress')}
            aria-valuemin={0}
            aria-valuemax={data.level_size}
            aria-valuenow={data.level_progress}
            className="h-6 overflow-hidden rounded-full bg-white shadow-inner"
          >
            <div
              className="h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
              style={{
                width: `${(data.level_progress / data.level_size) * 100}%`,
                backgroundColor: tokens.main,
              }}
            />
          </div>
          <p className="text-sm font-bold text-slate-600">
            {t('child_progress.earned', { count: data.earned_xp })} ·{' '}
            {t('child_progress.level_hint', { count: data.level_size })}
          </p>
        </div>
      ) : progress.isError ? (
        <Alert>{errorMessage(t, progress.error)}</Alert>
      ) : (
        <p role="status">{t('common.loading')}</p>
      )}
    </section>
  )
}
