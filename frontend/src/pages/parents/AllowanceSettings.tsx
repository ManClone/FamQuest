import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { api, apiGet } from '../../api/client'
import { useParentMutation } from '../../api/mutations'
import { Alert, Button, TextField } from '../../components/ui'
import { errorMessage } from '../../errors'
import { euroCents, euroInput } from '../../euro-input'

export function AllowanceSettings({ memberId }: { memberId: number }) {
  const { t } = useTranslation()
  const [opened, setOpened] = useState(false)
  const [input, setInput] = useState<string | null>(null)
  const state = useQuery({
    queryKey: ['criticism', memberId, 'allowance'],
    enabled: opened,
    queryFn: () =>
      apiGet<{ weekly_amount_cents: number | null }>(`/members/${memberId}/money/settings`),
  })
  const save = useParentMutation(
    (amount: number | null) =>
      api('PUT', `/members/${memberId}/money/settings`, {
        weekly_amount_cents: amount,
      }),
    [['criticism']],
  )
  const value = input ?? euroInput(state.data?.weekly_amount_cents ?? 0)
  const cents = euroCents(value)
  return (
    <details
      className="mt-4 border-t pt-3"
      onToggle={(event) => setOpened(event.currentTarget.open)}
    >
      <summary className="cursor-pointer font-bold">{t('criticism.allowance_settings')}</summary>
      {opened && (
        <div className="flex flex-col gap-3 pt-3">
          <p>{t('criticism.allowance_hint')}</p>
          {state.isError && <Alert>{errorMessage(t, state.error)}</Alert>}
          <TextField
            label={t('criticism.allowance_amount')}
            value={value}
            inputMode="decimal"
            maxLength={8}
            onChange={(event) => setInput(event.target.value)}
          />
          {cents === null && <Alert>{t('errors.validation.invalid')}</Alert>}
          {save.isError && <Alert>{errorMessage(t, save.error)}</Alert>}
          {save.isSuccess && <p role="status">{t('criticism.allowance_saved')}</p>}
          <Button
            variant="secondary"
            disabled={!state.isSuccess || cents === null || save.isPending}
            onClick={() => save.mutate(cents || null, { onSuccess: () => setInput(null) })}
          >
            {t('criticism.allowance_save')}
          </Button>
        </div>
      )}
    </details>
  )
}
