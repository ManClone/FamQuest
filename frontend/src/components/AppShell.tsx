import { type ComponentType, type SVGProps, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import BroomIcon from '~icons/fluent-emoji-flat/broom'
import GearIcon from '~icons/fluent-emoji-flat/gear'
import StarIcon from '~icons/fluent-emoji-flat/glowing-star'
import GiftIcon from '~icons/fluent-emoji-flat/wrapped-gift'
import HouseIcon from '~icons/fluent-emoji-flat/house-with-garden'

import { useMe } from '../api/auth'
import { useToday } from '../api/today'
import { usePhotos } from '../api/photos'
import { getFrameIdleMinutes } from '../frameIdle'
import { useIdleTimeout } from '../useIdleTimeout'

interface NavItemProps {
  to: string
  label: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  active: boolean
  className?: string
  /** Zahl im roten Kreis, z. B. wartende Kontrollen (0 = keine). */
  badge?: number
  badgeLabel?: string
}

function NavItem({
  to,
  label,
  icon: Icon,
  active,
  className = '',
  badge = 0,
  badgeLabel,
}: NavItemProps) {
  return (
    <Link
      to={to}
      aria-current={active ? 'page' : undefined}
      aria-label={badge > 0 && badgeLabel ? `${label}, ${badgeLabel}` : undefined}
      className={`flex min-h-20 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-3xl px-1 py-2 text-center text-xs leading-tight font-bold hyphens-auto sm:min-w-20 sm:hyphens-manual sm:flex-none sm:px-2 sm:text-sm focus-visible:outline-4 focus-visible:outline-orange-400 ${active ? 'bg-orange-100 text-orange-800' : 'text-slate-600 hover:bg-orange-50'} ${className}`}
    >
      <span className="relative">
        <Icon className="size-10" aria-hidden="true" />
        {badge > 0 && (
          <span
            aria-hidden="true"
            className="absolute -top-2 -right-3 flex min-w-7 items-center justify-center rounded-full bg-red-600 px-1.5 text-base leading-7 font-extrabold text-white ring-2 ring-white"
          >
            {badge}
          </span>
        )}
      </span>
      {label}
    </Link>
  )
}

/**
 * Rahmen des Alltagsbereichs: feste Navigationsleiste mit großen Symbolen,
 * links auf größeren Bildschirmen, unten am Smartphone (dort teilen sich die Symbole die Breite).
 */
export function AppShell() {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  // Die Personenansicht gehört zum Aufgabenbereich.
  const onTasks = pathname.startsWith('/tasks') || pathname.startsWith('/member/')
  const role = useMe().data?.user.role
  const isParent = role === 'admin' || role === 'parent'
  const today = useToday()
  const pending = isParent ? (today.data?.pending_approvals ?? 0) : 0
  const hasPhotos = usePhotos().data?.some((photo) => photo.visible) ?? false
  const [idleMinutes] = useState(getFrameIdleMinutes)
  const navigate = useNavigate()
  useIdleTimeout(isParent && hasPhotos && idleMinutes > 0 ? idleMinutes * 60 * 1000 : null, () =>
    navigate('/frame'),
  )

  return (
    <div className="flex min-h-dvh flex-col sm:flex-row">
      <nav
        aria-label={t('nav.label')}
        className="fixed inset-x-0 bottom-0 z-10 flex gap-2 border-t border-orange-100 bg-white/95 p-2 backdrop-blur sm:sticky sm:top-0 sm:h-dvh sm:w-28 sm:shrink-0 sm:flex-col sm:border-t-0 sm:border-r sm:p-3"
      >
        <NavItem
          to="/"
          label={t(isParent ? 'personal.dashboard' : 'nav.today')}
          icon={HouseIcon}
          active={pathname === '/'}
          badge={pending}
          badgeLabel={t('nav.pending', { count: pending })}
        />
        {isParent ? (
          <NavItem
            to="/household"
            label={t('nav.household')}
            icon={BroomIcon}
            active={pathname.startsWith('/household')}
          />
        ) : (
          <NavItem to="/tasks" label={t('nav.tasks')} icon={StarIcon} active={onTasks} />
        )}
        <NavItem
          to={isParent ? '/parents/rewards' : '/rewards'}
          label={t('nav.rewards')}
          icon={GiftIcon}
          active={pathname.startsWith('/rewards') || pathname.startsWith('/parents/rewards')}
        />
        <NavItem
          to="/settings"
          label={t('nav.settings')}
          icon={GearIcon}
          active={
            pathname === '/settings' ||
            (pathname.startsWith('/parents') && !pathname.startsWith('/parents/rewards'))
          }
        />
      </nav>
      <div className="flex min-w-0 flex-1 flex-col pb-28 sm:pb-0">
        <Outlet />
      </div>
    </div>
  )
}
