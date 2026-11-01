import { useApprovalMutation, undoConfirmedTask, undoConfirmedChore } from '../../api/approvals'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import CheckIcon from '~icons/fluent-emoji-flat/check-mark-button'
import GiftIcon from '~icons/fluent-emoji-flat/wrapped-gift'
import BackIcon from '~icons/fluent-emoji-flat/left-arrow'
import UndoIcon from '~icons/fluent-emoji-flat/counterclockwise-arrows-button'
import MinusCircleIcon from '~icons/fluent-emoji-flat/minus'
import PlusCircleIcon from '~icons/fluent-emoji-flat/plus'
import TrophyIcon from '~icons/fluent-emoji-flat/trophy'
import ManualIcon from '~icons/fluent-emoji-flat/writing-hand'

import { ApiError, api } from '../../api/client'
import { useParentMutation } from '../../api/mutations'
import type { Member } from '../../api/members'
import {
  MANUAL_MAX_POINTS,
  POINTS_KEY,
  PROGRESS_KEY,
  type PointKind,
  type PointTransaction,
  useBookPoints,
  usePointHistory,
} from '../../api/points'
import { Avatar } from '../../components/Avatar'
import { TaskIcon } from '../../components/TaskIcon'
import { Alert, Button, Section, TextField } from '../../components/ui'
import { errorMessage } from '../../errors'
import { ChoiceTile, Field, NumberStepper } from './formParts'

const KIND_ICONS: Record<PointKind, typeof ManualIcon> = {
  task_completed: CheckIcon,
  task_undone: UndoIcon,
  manual: ManualIcon,
  reward_redeemed: GiftIcon,
  reward_cancelled: UndoIcon,
  chore_completed: CheckIcon,
  chore_undone: UndoIcon,
  penalty_reversed: UndoIcon,
  manual_reversed: UndoIcon,
  consequence: MinusCircleIcon,
  consequence_reversed: UndoIcon,
}

type Direction = 'credit' | 'deduct'

interface PointsEditorProps {
  member: Member
  /** Zeitzone der Familie für Datum und Uhrzeit der Buchungen. */
  timeZone: string
  onBack?: () => void
  embedded?: boolean
}

/** Punktestand, Buchungshistorie und manuelle Buchung für eine Person. */
export function PointsEditor({ member, timeZone, onBack, embedded = false }: PointsEditorProps) {
  const { t } = useTranslation()
  const history = usePointHistory(member.id)
  const book = useBookPoints(member.id)
  const [direction, setDirection] = useState<Direction>('credit')
  const [amount, setAmount] = useState(1)
  const [reason, setReason] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [notice, setNotice] = useState<string>()
  const credit = member.role === 'child' || direction === 'credit'
  const Heading = embedded ? 'h2' : 'h1'

  const total = history.data?.pages[0]?.total
  const transactions = history.data?.pages.flatMap((page) => page.transactions) ?? []
  const reasonError =
    submitted && !reason.trim()
      ? errorMessage(t, 'validation.required')
      : book.error instanceof ApiError && book.error.fields.reason
        ? errorMessage(t, book.error.fields.reason)
        : undefined

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setSubmitted(true)
    setNotice(undefined)
    if (!reason.trim()) return
    book.mutate(
      { amount: credit ? amount : -amount, reason: reason.trim() },
      {
        onSuccess: () => {
          setNotice(
            t(credit ? 'points.credited' : 'points.deducted', {
              count: amount,
              name: member.name,
            }),
          )
          setAmount(1)
          setReason('')
          setSubmitted(false)
        },
      },
    )
  }

  return (
    <section
      className={
        embedded
          ? 'flex min-w-0 flex-col gap-6'
          : 'mx-auto flex min-h-dvh max-w-3xl flex-col gap-6 p-4 sm:p-6'
      }
    >
      {!embedded && (
        <Button variant="secondary" onClick={onBack} className="self-start">
          <BackIcon className="size-8" aria-hidden="true" />
          {t('actions.back')}
        </Button>
      )}
      {!embedded && (
        <header className="flex flex-wrap items-center gap-4">
          <Avatar name={member.name} color={member.color} src={member.avatar_url} size="lg" />
          <Heading className="min-w-0 flex-1 text-3xl font-extrabold break-words text-orange-600">
            {t('points.open', { name: member.name })}
          </Heading>
          <p className="flex items-center gap-2 rounded-2xl bg-white px-4 py-2 shadow-sm">
            <TrophyIcon className="size-10" aria-hidden="true" />
            <span className="sr-only">{t('points.balance')}: </span>
            <span className="text-4xl font-extrabold text-slate-800 tabular-nums">
              {total ?? '–'}
            </span>
          </p>
        </header>
      )}

      {notice && (
        <p
          role="status"
          className="rounded-2xl bg-emerald-100 px-4 py-3 text-lg font-semibold text-emerald-800"
        >
          {notice}
        </p>
      )}

      <form
        className="flex flex-col gap-6 rounded-3xl bg-white p-6 shadow-sm"
        onSubmit={submit}
        noValidate
      >
        <h2 className="text-2xl font-extrabold text-slate-800">
          {t(member.role === 'child' ? 'family_account.credit_title' : 'points.book_title')}
        </h2>
        {embedded && (
          <p className="flex items-center gap-2 font-bold text-slate-700">
            <TrophyIcon className="size-6" aria-hidden="true" />
            {t('points.balance')}: <span className="tabular-nums">{total ?? '–'}</span>
          </p>
        )}
        {book.isError && !(book.error instanceof ApiError && book.error.fields.reason) && (
          <Alert>{errorMessage(t, book.error)}</Alert>
        )}
        {member.role !== 'child' && (
          <Field label={t('points.direction')}>
            <div className="grid grid-cols-2 gap-3">
              <ChoiceTile
                name="direction"
                checked={direction === 'credit'}
                onChange={() => setDirection('credit')}
              >
                <PlusCircleIcon className="size-10" aria-hidden="true" />
                {t('points.credit')}
              </ChoiceTile>
              <ChoiceTile
                name="direction"
                checked={direction === 'deduct'}
                onChange={() => setDirection('deduct')}
              >
                <MinusCircleIcon className="size-10" aria-hidden="true" />
                {t('points.deduct')}
              </ChoiceTile>
            </div>
          </Field>
        )}
        <Field label={t('points.amount')}>
          <NumberStepper
            label={t('points.amount')}
            value={amount}
            min={1}
            max={MANUAL_MAX_POINTS}
            onChange={setAmount}
            decreaseLabel={t('tasks.fewer_points')}
            increaseLabel={t('tasks.more_points')}
          />
        </Field>
        <TextField
          label={t('points.reason')}
          hint={t('points.reason_hint')}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={200}
          autoComplete="off"
          error={reasonError}
        />
        <Button type="submit" className="self-start" disabled={book.isPending}>
          {t(credit ? 'points.submit_credit' : 'points.submit_deduct', {
            count: amount,
          })}
        </Button>
      </form>

      <Section title={t('points.history')}>
        {history.isError && <Alert>{errorMessage(t, history.error)}</Alert>}
        {history.isPending && (
          <p role="status" className="text-lg text-slate-600">
            {t('common.loading')}
          </p>
        )}
        {history.isSuccess && transactions.length === 0 && (
          <p className="text-lg text-slate-600">{t('points.history_empty')}</p>
        )}
        {transactions.length > 0 && (
          <ul className="flex max-h-96 flex-col divide-y divide-slate-100 overflow-y-auto">
            {transactions.map((transaction) => (
              <TransactionRow
                key={transaction.id}
                transaction={transaction}
                timeZone={timeZone}
                memberId={member.id}
              />
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
            {t('points.load_more')}
          </Button>
        )}
      </Section>
    </section>
  )
}

function TransactionRow({
  transaction,
  timeZone,
  memberId,
}: {
  transaction: PointTransaction
  timeZone: string
  memberId: number
}) {
  const { t, i18n } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [undoing, setUndoing] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const restore = useApprovalMutation(() =>
    api<void>('POST', `/activity-corrections/${transaction.restore_id}/restore`, {
      confirmed: true,
    }),
  )
  const undo = useApprovalMutation((id: number) =>
    transaction.undo_source === 'task' ? undoConfirmedTask(id) : undoConfirmedChore(id),
  )
  const [correction, setCorrection] = useState('')
  const reverse = useParentMutation(
    () =>
      api(
        'POST',
        transaction.correction_id != null
          ? `/activity-corrections/${transaction.correction_id}/deactivate`
          : `/members/${memberId}/points/${transaction.id}/reverse`,
        {
          ...(transaction.correction_id != null ? { confirmed: true } : {}),
          reason: correction.trim(),
        },
      ),
    [POINTS_KEY, PROGRESS_KEY, ['today']],
  )
  const language = i18n.resolvedLanguage ?? i18n.language
  const KindIcon = KIND_ICONS[transaction.kind] ?? ManualIcon
  const when = new Intl.DateTimeFormat(language, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(transaction.created_at))
  const positive = (transaction.amount || transaction.money_cents || 0) > 0

  const manualCredit =
    transaction.kind === 'manual' &&
    transaction.amount > 0 &&
    !transaction.reversed_at &&
    !transaction.inactive
  const canRestore = transaction.restore_id != null
  const canUndo = !!transaction.undo_source && transaction.undo_id != null
  const content = (
    <>
      <span className="shrink-0">
        {transaction.icon ? (
          <TaskIcon icon={transaction.icon} className="size-12" />
        ) : (
          <KindIcon className="size-12" aria-hidden="true" />
        )}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-lg font-bold break-words text-slate-800">{transaction.reason}</span>
        {transaction.inactive && (
          <span className="text-sm font-bold text-red-800">{t('family_account.inactive')}</span>
        )}
        {transaction.reactivated && (
          <span className="text-sm text-emerald-800">{t('family_account.reactivated')}</span>
        )}
        {transaction.reversed_at && (
          <span className="text-sm text-slate-600">
            {t('points.reversed', { id: transaction.reversal_transaction_id })} ·{' '}
            {transaction.reversal_reason}
          </span>
        )}
        {transaction.compensates_transaction_id && (
          <span className="text-sm text-slate-600">
            {t('points.compensates', { id: transaction.compensates_transaction_id })}
          </span>
        )}
        <span className="flex flex-wrap items-center gap-x-2 text-base text-slate-500">
          {transaction.icon && <KindIcon className="size-5" aria-hidden="true" />}
          {t(`points.kind_${transaction.kind}`)} · {when}
        </span>
      </span>
      <span
        className={`shrink-0 rounded-full px-3 py-1 text-xl font-extrabold tabular-nums ${transaction.inactive ? 'bg-red-100 text-red-800 line-through' : positive ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}
      >
        {transaction.amount === 0
          ? transaction.money_cents
            ? new Intl.NumberFormat(language, { style: 'currency', currency: 'EUR' }).format(
                transaction.money_cents / 100,
              )
            : '0'
          : positive
            ? `+${transaction.amount}`
            : `−${Math.abs(transaction.amount)}`}
      </span>
    </>
  )
  return (
    <li
      className={`flex flex-wrap items-center gap-3 py-3 ${transaction.inactive ? 'rounded-xl border border-red-200 bg-red-50' : ''}`}
    >
      {canRestore || canUndo || manualCredit ? (
        <button
          type="button"
          className="flex w-full min-w-0 items-center gap-3 rounded-xl p-2 text-left hover:bg-orange-50 focus-visible:outline-2 focus-visible:outline-orange-400"
          disabled={undo.isPending || reverse.isPending || restore.isPending}
          aria-expanded={canRestore ? restoring : canUndo ? undoing : correcting}
          onClick={() =>
            canRestore ? setRestoring(true) : canUndo ? setUndoing(true) : setCorrecting(true)
          }
        >
          {content}
        </button>
      ) : (
        <div className="flex w-full min-w-0 items-center gap-3">{content}</div>
      )}
      {canRestore && restoring && (
        <div className="flex w-full flex-col gap-3 rounded-xl bg-red-50 p-3">
          <p>{t('family_account.restore_confirm')}</p>
          {restore.isError && <Alert>{errorMessage(t, restore.error)}</Alert>}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={restore.isPending}
              onClick={() => restore.mutate(0, { onSuccess: () => setRestoring(false) })}
            >
              {t('family_account.restore')}
            </Button>
            <Button
              variant="secondary"
              disabled={restore.isPending}
              onClick={() => setRestoring(false)}
            >
              {t('actions.cancel')}
            </Button>
          </div>
        </div>
      )}
      {canUndo && undoing && (
        <div className="flex w-full flex-col gap-3 rounded-xl bg-orange-50 p-3">
          <p>{t('family_account.undo_confirm')}</p>
          {undo.isError && <Alert>{errorMessage(t, undo.error)}</Alert>}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={undo.isPending}
              onClick={() =>
                undo.mutate(transaction.undo_id!, { onSuccess: () => setUndoing(false) })
              }
            >
              {t('chore_history.yes')}
            </Button>
            <Button variant="secondary" disabled={undo.isPending} onClick={() => setUndoing(false)}>
              {t('actions.cancel')}
            </Button>
          </div>
        </div>
      )}
      {manualCredit && correcting && (
        <div className="w-full">
          <div className="flex flex-col gap-3 rounded-xl bg-orange-50 p-3">
            <p>{t('family_account.credit_hint', { count: transaction.amount })}</p>
            <TextField
              label={t('criticism.correction_reason')}
              value={correction}
              maxLength={200}
              onChange={(event) => setCorrection(event.target.value)}
            />
            {reverse.isError && <Alert>{errorMessage(t, reverse.error)}</Alert>}
            <Button
              disabled={!correction.trim() || reverse.isPending}
              onClick={() => reverse.mutate(undefined, { onSuccess: () => setCorrecting(false) })}
            >
              {t('family_account.confirm_credit')}
            </Button>
            <Button
              variant="secondary"
              disabled={reverse.isPending}
              onClick={() => setCorrecting(false)}
            >
              {t('actions.cancel')}
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}
