import { type ComponentType, type SVGProps, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import BroomIcon from '~icons/fluent-emoji-flat/broom'
import StarIcon from '~icons/fluent-emoji-flat/glowing-star'

import { useMe } from '../api/auth'
import { DEFAULT_FRAME_SETTINGS, useFrameSettings } from '../api/frame'
import { useToday } from '../api/today'
import { useIdleTimeout } from '../useIdleTimeout'
import { useNow } from '../useNow'
import { formatLongDate } from '../weekdays'
import { ChoresPage } from './ChoresPage'
import { NightScreen } from './frame/NightScreen'
import { isNightTime } from './frame/night'
import { RoutineWidget } from './home/RoutineWidget'
import { WeatherBadge } from './home/WeatherBadge'

export const KITCHEN_PATH = '/kitchen'
export const KITCHEN_DAYS = 7

/** So viele Tage zeigt die Küchenansicht ab heute; heute ist doppelt so breit. */
/** Nach so langer Ruhe zeigt die Ansicht wieder die Woche bzw. nachts wieder den Nachtbildschirm. */
export const KITCHEN_IDLE_MS = 2 * 60 * 1000

type Icon = ComponentType<SVGProps<SVGSVGElement>>

/** Die Seiten von links nach rechts; das Symbol in der Kopfzeile springt direkt hin. */
const PAGES: { id: string; label: string; icon: Icon }[] = [
  { id: 'tasks', label: 'nav.tasks', icon: StarIcon },
  { id: 'household', label: 'nav.household', icon: BroomIcon },
]

/**
 * Küchenansicht für ein kleines Tablet im Querformat, ohne Navigationsleiste: zuerst die nächsten
 * Aufgaben und Haushalt per Wisch (oder Symbol oben). Nach kurzer Ruhe stehen wieder die Aufgaben da.
 * Nachts gilt das Nachtfenster
 * des Bilderrahmens; ein Tipp weckt die Ansicht für kurze Zeit.
 */
export function KitchenPage() {
  const { t, i18n } = useTranslation()
  const timeZone = useMe().data?.family.timezone
  const today = useToday().data
  const settings = useFrameSettings().data ?? DEFAULT_FRAME_SETTINGS
  const now = useNow()
  const language = i18n.resolvedLanguage ?? i18n.language
  const time = new Intl.DateTimeFormat(language, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  }).format(now)

  const pages = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState(0)
  const [awake, setAwake] = useState(false)
  const night =
    settings.night_enabled && isNightTime(now, settings.night_start, settings.night_end, timeZone)

  const show = (index: number, behavior: ScrollBehavior = 'smooth') => {
    const element = pages.current
    // Ohne Layout (Tests) gibt es nichts zu scrollen; die Seite gilt trotzdem als gewählt.
    element?.scrollTo?.({ left: index * element.clientWidth, behavior })
    setPage(index)
  }

  useIdleTimeout(KITCHEN_IDLE_MS, () => {
    show(0, 'auto')
    setAwake(false)
  })

  return (
    <div className="flex h-dvh flex-col gap-2 p-2 sm:p-3">
      <header className="flex shrink-0 items-center gap-3">
        <nav aria-label={t('kitchen.pages')} className="flex gap-1">
          {PAGES.map(({ id, label, icon: PageIcon }, index) => (
            <button
              key={id}
              type="button"
              aria-label={t(label)}
              title={t(label)}
              aria-current={page === index ? 'page' : undefined}
              onClick={() => show(index)}
              className="flex size-14 items-center justify-center rounded-2xl opacity-50 hover:bg-white/80 focus-visible:outline-4 focus-visible:outline-orange-400 aria-[current]:bg-orange-100 aria-[current]:opacity-100"
            >
              <PageIcon className="size-9" aria-hidden="true" />
            </button>
          ))}
        </nav>
        {today && (
          <p className="min-w-0 truncate text-xl font-bold text-slate-600">
            {formatLongDate(language, today.date)}
          </p>
        )}
        <WeatherBadge />
        <p className="ml-auto text-4xl font-extrabold text-slate-800 tabular-nums">
          <span className="sr-only">{t('home.time')}: </span>
          <time>{time}</time>
        </p>
      </header>

      <div
        ref={pages}
        onScroll={(event) => {
          const { scrollLeft, clientWidth } = event.currentTarget
          if (clientWidth > 0) setPage(Math.round(scrollLeft / clientWidth))
        }}
        // `relative`: Absolut gesetzte Teile der Seiten (z. B. Texte nur für Screenreader) bleiben so im
        // Wischbereich, statt die ganze Seite am Tablet breiter als den Bildschirm zu machen.
        className="relative flex min-h-0 flex-1 snap-x snap-mandatory overflow-x-auto overscroll-x-contain [scrollbar-width:none]"
      >
        {PAGES.map(({ id, label }) => (
          <section
            key={id}
            aria-label={t(label)}
            className="flex w-full shrink-0 snap-start snap-always flex-col overflow-y-auto p-1"
          >
            {id === 'tasks' && <RoutineWidget from={KITCHEN_PATH} more={false} />}
            {id === 'household' && <ChoresPage />}
          </section>
        ))}
      </div>

      {night && !awake && (
        <button
          type="button"
          aria-label={t('kitchen.wake')}
          onClick={() => setAwake(true)}
          className="fixed inset-0 z-50 cursor-none overflow-hidden bg-black focus:outline-none"
        >
          <NightScreen style={settings.night_style} now={now} timeZone={timeZone} />
        </button>
      )}
    </div>
  )
}
