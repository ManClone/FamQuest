import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useChores } from '../api/chores'
import { useMembers } from '../api/members'
import { useToday } from '../api/today'
import { Section } from '../components/ui'
import { ApprovalsSection } from './parents/ApprovalsSection'

export function DashboardPage() {
  const { t } = useTranslation()
  const today = useToday().data
  const members = useMembers().data ?? []
  const chores = useChores()
  const active = chores.data?.chores.filter((chore) => chore.active) ?? []
  return (
    <main className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
      <h1 className="text-3xl font-extrabold text-orange-600">{t('personal.dashboard')}</h1>
      <ApprovalsSection members={members} today={today?.date} />
      {(['overdue', 'current'] as const).map((kind) => (
        <Section key={kind} title={t(`personal.${kind}`)}>
          <ul className="flex flex-col gap-2">
            {active
              .filter((chore) => (kind === 'overdue' ? chore.days_left < 0 : chore.days_left === 0))
              .map((chore) => (
                <li key={chore.id}>
                  <Link className="font-bold text-orange-800" to="/household">
                    {chore.title}
                  </Link>
                </li>
              ))}
          </ul>
          {kind === 'current' && (
            <ul className="flex flex-col gap-2">
              {today?.tasks
                .filter(
                  (task) =>
                    task.time_of_day === today.time_of_day ||
                    task.time_of_day === null ||
                    task.extra,
                )
                .map((task) => (
                  <li key={task.id}>
                    {task.title} ·{' '}
                    {task.member_ids
                      .map((id) => members.find((member) => member.id === id)?.name)
                      .filter(Boolean)
                      .join(', ')}
                  </li>
                ))}
            </ul>
          )}
        </Section>
      ))}
    </main>
  )
}
