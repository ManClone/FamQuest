import { type CSSProperties, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import './PraiseCelebration.css'

type Notice = { key: string; kind: 'praise' | 'deduct'; reason?: string | null; amount?: number }

export function PraiseCelebration({
  memberId,
  latestId,
  reason,
  deductionId = 0,
  deductionReason,
  deductionAmount = 0,
}: {
  memberId: number
  latestId: number
  reason?: string | null
  deductionId?: number
  deductionReason?: string | null
  deductionAmount?: number
}) {
  const { t } = useTranslation()
  const [notices, setNotices] = useState<Notice[]>([])
  const closeButton = useRef<HTMLButtonElement>(null)
  const active = notices[0]
  const dismiss = () => setNotices((items) => items.slice(1))
  useEffect(() => {
    const next: Notice[] = []
    for (const event of [
      { id: latestId, kind: 'praise' as const, reason, amount: undefined },
      {
        id: deductionId,
        kind: 'deduct' as const,
        reason: deductionReason,
        amount: deductionAmount,
      },
    ]) {
      const storageKey =
        event.kind === 'praise'
          ? `famquest-praise-seen-${memberId}`
          : `famquest-deduction-seen-${memberId}`
      try {
        const previous = localStorage.getItem(storageKey)
        localStorage.setItem(storageKey, String(Math.max(Number(previous) || 0, event.id)))
        if (previous !== null && event.id > Number(previous))
          next.push({ key: `${memberId}-${event.kind}-${event.id}`, ...event })
      } catch {
        /* Without persistent storage, avoid replaying every poll. */
      }
    }
    if (next.length) setNotices((items) => [...items, ...next])
  }, [memberId, latestId, reason, deductionId, deductionReason, deductionAmount])
  useEffect(() => {
    if (!active) return
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus()
    const close = () => setNotices((items) => items.slice(1))
    const timer = setTimeout(close, 10000)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
      if (event.key === 'Tab') {
        event.preventDefault()
        closeButton.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
      previousFocus?.focus()
    }
  }, [active?.key])
  if (!active) return null
  const praise = active.kind === 'praise'
  return createPortal(
    <div
      key={active.key}
      className={`reward-notice ${praise ? 'is-praise' : 'is-deduction'}`}
      role="dialog"
      aria-modal="true"
      aria-label={t(praise ? 'praise.received' : 'praise.deducted')}
    >
      <div className="notice-effects" aria-hidden="true">
        {praise
          ? Array.from({ length: 7 }, (_, burst) => (
              <div
                className="notice-burst"
                key={burst}
                style={
                  {
                    '--x': `${12 + ((burst * 29) % 80)}%`,
                    '--y': `${14 + ((burst * 19) % 70)}%`,
                    '--delay': `${(burst % 4) * 0.45}s`,
                    '--hue': `${(burst * 57) % 360}`,
                  } as CSSProperties
                }
              >
                {Array.from({ length: 12 }, (_, ray) => (
                  <i key={ray} style={{ '--angle': `${ray * 30}deg` } as CSSProperties} />
                ))}
              </div>
            ))
          : Array.from({ length: 12 }, (_, n) => (
              <span
                className="notice-flying-star"
                key={n}
                style={
                  {
                    '--dx': `${(n % 2 ? 1 : -1) * (18 + n * 3)}vw`,
                    '--dy': `${-18 - (n % 5) * 12}vh`,
                    '--delay': `${n * 0.08}s`,
                  } as CSSProperties
                }
              >
                ⭐
              </span>
            ))}
      </div>
      <div className="notice-card">
        <div aria-hidden="true" className="notice-character">
          {praise ? (
            '❤️'
          ) : (
            <>
              <span className="notice-face">😮</span>
              <span className="notice-hand">👋</span>
            </>
          )}
        </div>
        <h2 className="text-2xl font-extrabold sm:text-4xl">
          {t(praise ? 'praise.received' : 'praise.deducted')}
        </h2>
        {!praise && (
          <p className="mt-3 text-3xl font-extrabold text-amber-700">−{active.amount} ⭐</p>
        )}
        {active.reason && (
          <p className="mt-4 text-lg font-semibold break-words sm:text-2xl">{active.reason}</p>
        )}
        <button
          ref={closeButton}
          type="button"
          onClick={dismiss}
          className="mt-6 min-h-11 rounded-full bg-slate-800 px-6 py-3 font-bold text-white focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-orange-400"
        >
          {t('actions.close')}
        </button>
      </div>
    </div>,
    document.body,
  )
}
