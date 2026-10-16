import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useConfirmedChores, undoConfirmedChore, useApprovalMutation } from '../../api/approvals'
import type { Member } from '../../api/members'
import { TaskIcon } from '../../components/TaskIcon'
import { Alert, Button } from '../../components/ui'
import { errorMessage } from '../../errors'
import { formatLongDate } from '../../weekdays'

export function ConfirmedChores({ members }: { members: Member[] }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<number>()
  const history = useConfirmedChores(open)
  const undo = useApprovalMutation(undoConfirmedChore)
  const items = history.data?.pages.flatMap((page) => page.items) ?? []
  return (
    <details
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className="rounded-2xl border border-slate-200 bg-white p-3"
    >
      <summary className="cursor-pointer py-2 font-bold">{t('chore_history.title')}</summary>
      {open && (
        <div className="mt-2 flex flex-col gap-3">
          <p className="text-sm text-slate-500">{t('chore_history.intro')}</p>
          {history.isPending && <p>{t('chore_history.loading')}</p>}
          {history.error && <Alert>{errorMessage(t, history.error)}</Alert>}
          {undo.error && <Alert>{errorMessage(t, undo.error)}</Alert>}
          {history.isSuccess && items.length === 0 && <p>{t('chore_history.empty')}</p>}
          <div
            role="region"
            aria-label={t('chore_history.title')}
            tabIndex={0}
            className="max-h-[min(60dvh,24rem)] overflow-y-auto overscroll-contain pr-2 [scrollbar-gutter:stable] focus-visible:outline-2 focus-visible:outline-orange-400"
          >
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="flex min-w-0 flex-wrap items-center gap-3 rounded-xl bg-orange-50 p-3"
                >
                  <TaskIcon icon={item.icon} className="size-9 shrink-0" />
                  <div className="min-w-0 flex-1 basis-40">
                    <p className="font-bold break-words">{item.title}</p>
                    <p className="text-sm text-slate-600">
                      {members.find((member) => member.id === item.member_id)?.name ?? '?'} ·{' '}
                      {formatLongDate(i18n.resolvedLanguage ?? i18n.language, item.date)}
                    </p>
                    <p className="text-sm text-slate-500">
                      {new Date(item.completed_at).toLocaleTimeString(i18n.language)} · ⭐{' '}
                      {item.points}
                    </p>
                  </div>
                  {selected !== item.id ? (
                    <Button
                      variant="secondary"
                      disabled={undo.isPending}
                      size="compact"
                      onClick={() => setSelected(item.id)}
                    >
                      {t('chore_history.undo')}
                    </Button>
                  ) : (
                    <div className="w-full">
                      <p className="mb-2 font-semibold">{t('chore_history.confirm')}</p>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="danger"
                          disabled={undo.isPending}
                          onClick={() =>
                            undo.mutate(item.id, { onSuccess: () => setSelected(undefined) })
                          }
                        >
                          {t('chore_history.yes')}
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={undo.isPending}
                          onClick={() => setSelected(undefined)}
                        >
                          {t('chore_history.cancel')}
                        </Button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
            {history.hasNextPage && (
              <Button
                variant="secondary"
                disabled={history.isFetchingNextPage}
                onClick={() => history.fetchNextPage()}
              >
                {t('chore_history.more')}
              </Button>
            )}
          </div>
        </div>
      )}
    </details>
  )
}
