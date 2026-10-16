import { PenaltyHistory, PENALTY_HISTORY_KEY } from './PenaltyHistory'
import { PraiseHistory, PRAISE_HISTORY_KEY } from './PraiseHistory'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import type { Member } from '../../api/members'
import { useParentMutation } from '../../api/mutations'
import { bookPoints, POINTS_KEY, PROGRESS_KEY, useMemberProgress } from '../../api/points'
import { TODAY_KEY } from '../../api/today'
import { Avatar } from '../../components/Avatar'
import { Alert, Button, Section, TextField } from '../../components/ui'
import { errorMessage } from '../../errors'

export function EncouragementPanel({ members }: { members: Member[] }) {
  const { t } = useTranslation()
  const children = members.filter((member) => member.role === 'child')
  const [selected, setSelected] = useState<number>()
  const child = children.find((member) => member.id === selected) ?? children[0]
  if (!child) return null
  return (
    <Section title={t('praise.section')}>
      {children.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {children.map((member) => (
            <Button
              key={member.id}
              variant={member.id === child.id ? 'primary' : 'secondary'}
              onClick={() => setSelected(member.id)}
            >
              {member.name}
            </Button>
          ))}
        </div>
      )}
      <EncouragementForm key={child.id} member={child} />
    </Section>
  )
}

function EncouragementForm({ member }: { member: Member }) {
  const { t } = useTranslation()
  const progress = useMemberProgress(member.id)
  const [mode, setMode] = useState<'praise' | 'deduct' | null>(null)
  const [reason, setReason] = useState('')
  const [amount, setAmount] = useState(1)
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID().replaceAll('-', ''))
  const [saved, setSaved] = useState(false)
  const save = useParentMutation(async () => {
    if (mode === 'praise')
      return api('POST', `/members/${member.id}/praise`, {
        reason: reason.trim(),
        request_key: requestKey,
      })
    return bookPoints(member.id, { amount: -amount, reason: reason.trim() })
  }, [POINTS_KEY, PROGRESS_KEY, TODAY_KEY, PRAISE_HISTORY_KEY, PENALTY_HISTORY_KEY])
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!mode || !reason.trim()) return
    setSaved(false)
    save.mutate(undefined, {
      onSuccess: () => {
        setSaved(true)
        setMode(null)
        setReason('')
        setRequestKey(crypto.randomUUID().replaceAll('-', ''))
      },
    })
  }
  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <Avatar name={member.name} color={member.color} src={member.avatar_url} size="xs" />
          <span className="min-w-0 flex-1 truncate text-lg font-bold">{member.name}</span>
          <span
            className="rounded-full bg-rose-50 px-3 py-1 font-bold text-rose-700"
            aria-label={t('praise.count', { count: progress.data?.praise_count ?? 0 })}
          >
            ❤️ {progress.data?.praise_count ?? 0}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button
            size="compact"
            disabled={save.isPending}
            aria-expanded={mode === 'praise'}
            variant={mode === 'praise' ? 'primary' : 'secondary'}
            onClick={() => {
              setMode('praise')
              setSaved(false)
            }}
          >
            <span aria-hidden="true">❤️</span> {t('praise.give')}
          </Button>
          <Button
            size="compact"
            disabled={save.isPending}
            aria-expanded={mode === 'deduct'}
            variant={mode === 'deduct' ? 'danger' : 'secondary'}
            onClick={() => {
              setMode('deduct')
              setSaved(false)
            }}
          >
            {t('praise.deduct')}
          </Button>
        </div>
        {mode && (
          <div className="flex flex-col gap-3 rounded-2xl bg-orange-50 p-3">
            {mode === 'deduct' && (
              <TextField
                label={t('praise.amount')}
                type="number"
                min={1}
                max={1000}
                step={1}
                required
                value={amount}
                onChange={(event) => setAmount(Number(event.target.value))}
              />
            )}
            <TextField
              label={t('praise.reason')}
              required
              maxLength={200}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <Button
              type="submit"
              disabled={save.isPending || !reason.trim()}
              size="compact"
              className="self-start"
            >
              {t(mode === 'praise' ? 'praise.give' : 'praise.deduct')}
            </Button>
            <Button
              size="compact"
              variant="secondary"
              disabled={save.isPending}
              className="self-start"
              onClick={() => {
                setMode(null)
                setReason('')
              }}
            >
              {t('actions.cancel')}
            </Button>
          </div>
        )}
        {save.error ? <Alert>{errorMessage(t, save.error)}</Alert> : null}
        {saved && <p role="status">{t('praise.saved')}</p>}
      </form>
      <PraiseHistory memberId={member.id} />
      <PenaltyHistory memberId={member.id} />
    </>
  )
}
