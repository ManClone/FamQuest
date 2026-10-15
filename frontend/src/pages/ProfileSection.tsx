import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { useLogout } from '../api/auth'
import { api, apiGet } from '../api/client'
import type { Member } from '../api/members'
import { Avatar } from '../components/Avatar'
import { AvatarCropper } from '../components/AvatarCropper'
import { Alert, Button, Section, TextField } from '../components/ui'
import { errorMessage } from '../errors'

export function ProfileSection() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const profile = useQuery({
    queryKey: ['profile'],
    queryFn: () => apiGet<{ email: string; member: Member | null }>('/profile'),
  })
  const [name, setName] = useState<string | undefined>()
  const [cropFile, setCropFile] = useState<File | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [repeatPassword, setRepeatPassword] = useState('')
  const [notice, setNotice] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const logout = useLogout()
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['profile'] })
    void queryClient.invalidateQueries({ queryKey: ['members'] })
  }
  const save = useMutation({
    mutationFn: () => api('PUT', '/profile', { name: name ?? profile.data?.member?.name }),
    onSuccess: () => {
      refresh()
      setNotice(t('personal.saved'))
    },
  })
  const photo = useMutation({
    mutationFn: (image: Blob | null) =>
      image ? api('PUT', '/profile/avatar', image) : api('DELETE', '/profile/avatar'),
    onSuccess: () => {
      refresh()
      setCropFile(null)
      setNotice(t('personal.saved'))
    },
  })
  const password = useMutation({
    mutationFn: () =>
      api('PUT', '/profile/password', {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: () => {
      setCurrentPassword('')
      setNewPassword('')
      setRepeatPassword('')
      setNotice(t('personal.password_saved'))
    },
  })
  const member = profile.data?.member

  return (
    <>
      <Section title={t('personal.profile')}>
        {profile.isPending && <p>{t('common.loading')}</p>}
        {profile.isError && <Alert>{errorMessage(t, profile.error)}</Alert>}
        {profile.data && !member && <p>{t('personal.not_linked')}</p>}
        {member && (
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate()
            }}
          >
            <Avatar name={member.name} color={member.color} src={member.avatar_url} size="xl" />
            <TextField
              label={t('members.name')}
              value={name ?? member.name}
              required
              maxLength={50}
              onChange={(event) => setName(event.target.value)}
            />
            <input
              className="hidden"
              ref={fileInput}
              type="file"
              accept="image/*"
              aria-label={t('members.choose_photo')}
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (file) setCropFile(file)
              }}
            />
            <div className="flex flex-wrap gap-3">
              <Button type="button" variant="secondary" onClick={() => fileInput.current?.click()}>
                {t('members.choose_photo')}
              </Button>
              {member.avatar_url && (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={photo.isPending}
                  onClick={() => photo.mutate(null)}
                >
                  {t('members.remove_photo')}
                </Button>
              )}
              <Button type="submit" disabled={save.isPending}>
                {t('actions.save')}
              </Button>
            </div>
          </form>
        )}
        {save.isError && <Alert>{errorMessage(t, save.error)}</Alert>}
        {photo.isError && <Alert>{errorMessage(t, photo.error)}</Alert>}
        {cropFile && (
          <AvatarCropper
            file={cropFile}
            onCancel={() => setCropFile(null)}
            onConfirm={(image) => photo.mutate(image)}
          />
        )}
      </Section>
      <Section title={t('personal.access')}>
        <p>{profile.data?.email}</p>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (newPassword === repeatPassword) password.mutate()
          }}
        >
          <TextField
            label={t('personal.current_password')}
            type="password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
          <TextField
            label={t('personal.new_password')}
            type="password"
            autoComplete="new-password"
            minLength={10}
            required
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
          <TextField
            label={t('setup.password_repeat')}
            type="password"
            autoComplete="new-password"
            required
            value={repeatPassword}
            onChange={(event) => setRepeatPassword(event.target.value)}
          />
          {repeatPassword && newPassword !== repeatPassword && (
            <Alert>{t('personal.password_mismatch')}</Alert>
          )}
          {password.isError && <Alert>{errorMessage(t, password.error)}</Alert>}
          <Button
            type="submit"
            disabled={password.isPending || !newPassword || newPassword !== repeatPassword}
          >
            {t('personal.change_password')}
          </Button>
        </form>
        <Button
          variant="secondary"
          disabled={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
        >
          {t('actions.logout')}
        </Button>
      </Section>
      {notice && <p role="status">{notice}</p>}
    </>
  )
}
