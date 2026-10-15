import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useMe } from '../api/auth'
import { ProfileSection } from './ProfileSection'
import { DeviceSection } from './parents/DeviceSection'

export function SettingsPage() {
  const { t } = useTranslation()
  const parent = useMe().data?.user.role !== 'child'
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <h1 className="text-3xl font-extrabold text-orange-600">{t('nav.settings')}</h1>
      <ProfileSection />
      <DeviceSection personalOnly />
      {parent && (
        <section className="flex flex-col gap-3 rounded-3xl bg-white p-6">
          <h2 className="text-2xl font-bold">{t('personal.manage_family')}</h2>
          {(['family', 'tasks', 'household', 'rewards', 'settings'] as const).map((area) => (
            <Link
              key={area}
              className="rounded-xl bg-orange-50 p-4 text-lg font-bold text-orange-800"
              to={`/parents/${area}`}
            >
              {t(`parents_nav.${area}`)}
            </Link>
          ))}
        </section>
      )}
    </main>
  )
}
