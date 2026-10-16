import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, apiGet } from '../api/client'
import { useParentMutation } from '../api/mutations'
import { TaskIcon } from '../components/TaskIcon'
import { Alert, Button, Section } from '../components/ui'
import { errorMessage } from '../errors'

interface ChildChore {
  id: number
  title: string
  icon: string
  points: number
  repeatable: boolean
  days_left: number
  done_today: boolean
  count: number
  pending: number
}
export function ChildHouseholdTasks({ currentOnly }: { currentOnly: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['my-chores'],
    queryFn: () => apiGet<ChildChore[]>('/chores/mine'),
    refetchInterval: 60000,
  })
  const complete = useParentMutation(
    async (item: ChildChore) => {
      const request_key = Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
        byte.toString(16).padStart(2, '0'),
      ).join('')
      const result = await api<ChildChore[]>('PUT', `/chores/mine/${item.id}/done`, { request_key })
      queryClient.setQueryData(['my-chores'], result)
    },
    [['my-chores'], ['today']],
  )
  const chores = (query.data ?? []).filter(
    (item) => !currentOnly || item.days_left <= 0 || item.pending || item.count,
  )
  if (!chores.length && !query.isError) return null
  return (
    <Section title={t('chores.title')}>
      {query.isError && <Alert>{errorMessage(t, query.error)}</Alert>}
      {complete.isError && <Alert>{errorMessage(t, complete.error)}</Alert>}
      <ul className="grid gap-3 sm:grid-cols-2">
        {chores.map((item) => (
          <li
            key={item.id}
            className="flex min-w-0 flex-col gap-3 rounded-2xl border-2 border-orange-100 p-4"
          >
            <div className="flex items-center gap-3">
              <TaskIcon icon={item.icon} className="size-12" />
              <div className="min-w-0">
                <h3 className="text-xl font-extrabold break-words">{item.title}</h3>
                <p className="font-bold text-amber-700">⭐ {item.points}</p>
              </div>
            </div>
            {item.pending > 0 && (
              <p className="text-base font-semibold text-orange-700">
                {t('chores.awaiting', { count: item.pending })}
              </p>
            )}
            {item.count > 0 && <p>{t('chores.today_count', { count: item.count })}</p>}
            <Button
              disabled={
                complete.isPending || (!item.repeatable && (item.done_today || item.pending > 0))
              }
              onClick={() => complete.mutate(item)}
            >
              {t(
                item.count || item.done_today
                  ? item.repeatable
                    ? 'chores.repeat'
                    : 'chores.done_title'
                  : 'chores.child_complete',
              )}
            </Button>
          </li>
        ))}
      </ul>
    </Section>
  )
}
