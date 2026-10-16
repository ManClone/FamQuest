import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { NAV_POSITION_CLASSES } from '../../components/navigationStyles'
import { AREA_ICONS, PRIMARY_AREAS, type ParentArea, areaPath } from './areas'

/** Management replaces the everyday tabs, on desktop and mobile. */
export function ParentsNav({ area }: { area: ParentArea }) {
  const { t } = useTranslation()
  return (
    <nav
      aria-label={t('parents_nav.label')}
      className={`${NAV_POSITION_CLASSES} z-20 gap-1 bg-white p-2 sm:w-64 sm:p-3`}
    >
      {PRIMARY_AREAS.map((candidate) => {
        const Icon = AREA_ICONS[candidate]
        return (
          <Link
            key={candidate}
            to={areaPath(candidate)}
            aria-current={candidate === area ? 'page' : undefined}
            className="flex min-h-18 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-1 py-2 text-center text-xs font-bold text-slate-700 hover:bg-orange-50 focus-visible:outline-4 focus-visible:outline-orange-400 aria-[current=page]:bg-orange-100 aria-[current=page]:text-orange-800 sm:min-h-16 sm:flex-none sm:flex-row sm:justify-start sm:gap-3 sm:px-3 sm:text-left sm:text-lg"
          >
            <Icon className="size-8 shrink-0 sm:size-9" aria-hidden="true" />
            <span className="max-w-full break-words hyphens-auto">
              {t(`parents_nav.${candidate}`)}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
