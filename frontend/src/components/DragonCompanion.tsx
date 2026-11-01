import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import DragonIcon from '~icons/fluent-emoji-flat/dragon'

import { api } from '../api/client'
import type { Member } from '../api/members'
import { useParentMutation } from '../api/mutations'
import { PROGRESS_KEY, useMemberProgress } from '../api/points'
import { errorMessage } from '../errors'
import { Alert, Button, TextField } from './ui'

export function DragonCompanion({
  member,
  compact = false,
  showLevel = true,
}: {
  member: Member
  compact?: boolean
  showLevel?: boolean
}) {
  const { t } = useTranslation()
  const progress = useMemberProgress(member.id)
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const save = useParentMutation(
    () => api('PUT', `/members/${member.id}/dragon`, { name: name.trim() }),
    [PROGRESS_KEY],
  )
  if (member.role !== 'child' || !progress.data) return null
  const data = progress.data
  return (
    <section
      aria-label={t('dragon.of', { name: member.name })}
      className="flex min-w-0 flex-col gap-3 rounded-3xl border border-emerald-100 bg-emerald-50 p-4"
    >
      <div className="flex min-w-0 items-center gap-4">
        <DragonIcon
          className={compact ? 'size-20 shrink-0' : 'size-28 shrink-0'}
          aria-hidden="true"
        />
        <div className="min-w-0">
          <p className="text-sm font-bold text-emerald-800">{t('dragon.title')}</p>
          <h2 className="text-2xl font-extrabold break-words text-slate-800">
            {data.dragon_name || t('dragon.unnamed')}
          </h2>
          {showLevel && (
            <p className="font-bold text-emerald-800">
              {t('child_progress.level', { level: data.level ?? 1 })}
            </p>
          )}
          {!compact && <p className="text-sm text-slate-600">{t('dragon.hint')}</p>}
        </div>
      </div>
      {!data.dragon_name && !naming && (
        <Button variant="secondary" onClick={() => setNaming(true)}>
          {t('dragon.name_action')}
        </Button>
      )}
      {!data.dragon_name && naming && (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (name.trim()) save.mutate(undefined, { onSuccess: () => setNaming(false) })
          }}
        >
          <TextField
            label={t('dragon.name')}
            value={name}
            maxLength={24}
            onChange={(event) => setName(event.target.value)}
            hint={t('dragon.name_hint')}
          />
          {save.isError && <Alert>{errorMessage(t, save.error)}</Alert>}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={!name.trim() || save.isPending}>
              {t('dragon.save')}
            </Button>
            <Button variant="secondary" disabled={save.isPending} onClick={() => setNaming(false)}>
              {t('actions.cancel')}
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
