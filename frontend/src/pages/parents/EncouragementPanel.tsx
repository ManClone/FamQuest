import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import type { Member } from '../../api/members'
import { useParentMutation } from '../../api/mutations'
import { bookPoints, POINTS_KEY, PROGRESS_KEY, useMemberProgress } from '../../api/points'
import { TODAY_KEY } from '../../api/today'
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
      <EncouragementForm key={child.id} member={child} />
    </Section>
  )
}

function EncouragementForm({ member }: { member: Member }) {
  const { t } = useTranslation()
  const progress = useMemberProgress(member.id)
  const [mode, setMode] = useState<'praise' | 'deduct'>('praise')
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
  }, [POINTS_KEY, PROGRESS_KEY, TODAY_KEY])
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!reason.trim()) return
    setSaved(false)
    save.mutate(undefined, {
      onSuccess: () => {
        setSaved(true)
        setReason('')
        setRequestKey(crypto.randomUUID().replaceAll('-', ''))
      },
    })
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <p
        className="font-bold text-rose-700"
        aria-label={t('praise.count', { count: progress.data?.praise_count ?? 0 })}
      >
        ❤️ {progress.data?.praise_count ?? 0}
      </p>
      {progress.data?.latest_praise_reason && (
        <p className="text-sm text-slate-500">{progress.data.latest_praise_reason}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={mode === 'praise' ? 'primary' : 'secondary'}
          onClick={() => {
            setMode('praise')
            setSaved(false)
          }}
        >
          ❤️ {t('praise.give')}
        </Button>
        <Button
          variant={mode === 'deduct' ? 'danger' : 'secondary'}
          onClick={() => {
            setMode('deduct')
            setSaved(false)
          }}
        >
          {t('praise.deduct')}
        </Button>
      </div>
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
      <Button type="submit" disabled={save.isPending || !reason.trim()} className="self-start">
        {t(mode === 'praise' ? 'praise.give' : 'praise.deduct')}
      </Button>
      {save.error ? <Alert>{errorMessage(t, save.error)}</Alert> : null}
      {saved && <p role="status">{t('praise.saved')}</p>}
    </form>
  )
}
