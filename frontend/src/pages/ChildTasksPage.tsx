import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useMe } from '../api/auth'
import { useTasks } from '../api/tasks'
import { daysUntilDue, pointsFor } from '../api/today'
import { TaskIcon } from '../components/TaskIcon'
import { Alert, Section } from '../components/ui'
import { errorMessage } from '../errors'
import { ViewToggle } from './family/ViewToggle'
import { TaskGroups } from './family/TaskGroups'
import { tasksFor, useFamilyToday } from './family/useFamilyToday'

export function ChildTasksPage({ currentOnly = false }: { currentOnly?: boolean }) {
  const { t } = useTranslation()
  const me = useMe().data
  const { members, today, isPending, error } = useFamilyToday()
  const assigned = useTasks()
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
  const tasks = tasksFor(today.tasks, member.id).filter(
    (task) =>
      !currentOnly ||
      task.time_of_day === today.time_of_day ||
      task.time_of_day === null ||
      task.extra ||
      (daysUntilDue(task, member.id, today.date) ?? 0) < 0,
  )
  return (
    <main className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
      <h1 className="text-3xl font-extrabold text-orange-600">
        {currentOnly ? t('nav.today') : member.name}
      </h1>
      <p className="text-2xl font-bold">
        {t('personal.my_points', { count: pointsFor(today, member.id).total })}
      </p>
      {!currentOnly && <ViewToggle current="day" />}
      <TaskGroups
        member={member}
        tasks={tasks}
        date={today.date}
        currentTimeOfDay={today.time_of_day}
        size="lg"
      />
      {!currentOnly && (
        <Section title={t('personal.all_tasks')}>
          {assigned.isError && <Alert>{errorMessage(t, assigned.error)}</Alert>}
          <ul className="flex flex-col gap-3">
            {assigned.data?.map((task) => (
              <li key={task.id} className="flex items-center gap-3 rounded-2xl bg-orange-50 p-3">
                <TaskIcon icon={task.icon} className="size-12" />
                <div>
                  <strong>{task.title}</strong>
                  <p>
                    {t('tasks.points_count', { count: task.points })} ·{' '}
                    {t(
                      task.extra
                        ? 'tasks.extra'
                        : task.time_of_day
                          ? `times_of_day.${task.time_of_day}`
                          : 'tasks.anytime',
                    )}{' '}
                    · {t(`tasks.kind_${task.recurrence.kind}`)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </main>
  )
}
