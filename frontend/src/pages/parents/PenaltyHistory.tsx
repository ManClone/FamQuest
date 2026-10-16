import { useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, apiGet } from '../../api/client'
import { useParentMutation } from '../../api/mutations'
import { POINTS_KEY, PROGRESS_KEY } from '../../api/points'
import { TODAY_KEY } from '../../api/today'
import { Alert, Button, TextField } from '../../components/ui'
import { errorMessage } from '../../errors'

type Entry = {
  id: number
  reason: string
  amount: number
  created_at: string
  reversed_at: string | null
  reversal_reason: string | null
}
export const PENALTY_HISTORY_KEY = ['penalty-history'] as const
export function PenaltyHistory({ memberId }: { memberId: number }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<number>()
  const [reason, setReason] = useState('')
  const history = useInfiniteQuery({
    queryKey: [...PENALTY_HISTORY_KEY, memberId],
    queryFn: ({ pageParam }) =>
      apiGet<{ penalties: Entry[]; has_more: boolean }>(
        `/members/${memberId}/penalties${pageParam === null ? '' : `?before=${pageParam}`}`,
      ),
    initialPageParam: null as number | null,
    getNextPageParam: (page) => (page.has_more ? page.penalties.at(-1)?.id : undefined),
    enabled: open,
  })
  const revoke = useParentMutation(
    (id: number) =>
      api('POST', `/members/${memberId}/penalties/${id}/reverse`, { reason: reason.trim() }),
    [PENALTY_HISTORY_KEY, POINTS_KEY, PROGRESS_KEY, TODAY_KEY],
  )
  const entries = history.data?.pages.flatMap((page) => page.penalties) ?? []
  return (
    <details
      className="rounded-2xl border border-slate-200 p-3"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer py-1 font-bold">{t('penalty.history')}</summary>
      {open && (
        <div className="mt-3 flex flex-col gap-3">
          {history.isPending && <p>{t('common.loading')}</p>}
          {history.error && <Alert>{errorMessage(t, history.error)}</Alert>}
          {revoke.error && <Alert>{errorMessage(t, revoke.error)}</Alert>}
          {history.isSuccess && entries.length === 0 && <p>{t('penalty.empty')}</p>}
          <ul className="flex flex-col gap-3">
            {entries.map((entry) => (
              <li key={entry.id} className="min-w-0 rounded-xl bg-rose-50 p-3">
                <p className="font-semibold break-words">
                  −{entry.amount} ⭐ · {entry.reason}
                </p>
                <p className="text-sm text-slate-500">
                  {new Date(entry.created_at).toLocaleString(i18n.language)}
                </p>
                {entry.reversed_at ? (
                  <p className="mt-2 text-sm text-slate-600">
                    {t('penalty.reversed')} · {entry.reversal_reason}
                  </p>
                ) : selected === entry.id ? (
                  <div className="mt-3 flex flex-col gap-2">
                    <TextField
                      label={t('penalty.reason')}
                      value={reason}
                      maxLength={200}
                      onChange={(event) => setReason(event.target.value)}
                      disabled={revoke.isPending}
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="compact"
                        variant="danger"
                        disabled={!reason.trim() || revoke.isPending}
                        onClick={() =>
                          revoke.mutate(entry.id, {
                            onSuccess: () => {
                              setSelected(undefined)
                              setReason('')
                            },
                          })
                        }
                      >
                        {t('penalty.reverse')}
                      </Button>
                      <Button
                        size="compact"
                        variant="secondary"
                        disabled={revoke.isPending}
                        onClick={() => setSelected(undefined)}
                      >
                        {t('actions.cancel')}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    size="compact"
                    variant="secondary"
                    className="mt-2"
                    disabled={revoke.isPending}
                    onClick={() => {
                      setSelected(entry.id)
                      setReason('')
                    }}
                  >
                    {t('penalty.reverse')}
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {history.hasNextPage && (
            <Button
              size="compact"
              variant="secondary"
              disabled={history.isFetchingNextPage}
              onClick={() => history.fetchNextPage()}
            >
              {t('chore_history.more')}
            </Button>
          )}
        </div>
      )}
    </details>
  )
}
