import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router'
import { useMe } from '../api/auth'
import { AccountSection, ProfileSection } from './ProfileSection'
import { DeviceSection } from './parents/DeviceSection'

export function PersonalSettings() {
  const child = useMe().data?.user.role === 'child'
  return (
    <>
      <ProfileSection />
      <DeviceSection personalOnly={child} />
      <AccountSection />
    </>
  )
}

export function SettingsPage() {
  const { t } = useTranslation()
  const parent = useMe().data?.user.role !== 'child'
  if (parent) return <Navigate to="/parents/profile" replace />
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <h1 className="text-3xl font-extrabold text-orange-600">{t('nav.settings')}</h1>
      <PersonalSettings />
    </main>
  )
}
