import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

export function PraiseCelebration({
  memberId,
  latestId,
  reason,
}: {
  memberId: number
  latestId: number
  reason?: string | null
}) {
  const { t } = useTranslation()
  const [show, setShow] = useState(false)
  useEffect(() => {
    const key = `famquest-praise-seen-${memberId}`
    let previous: string | null = null
    try {
      previous = localStorage.getItem(key)
      localStorage.setItem(key, String(latestId))
    } catch {
      return
    }
    if (previous !== null && latestId > Number(previous)) setShow(true)
  }, [memberId, latestId])
  useEffect(() => {
    if (!show) return
    const timeout = setTimeout(() => setShow(false), 7000)
    return () => clearTimeout(timeout)
  }, [show])
  if (!show) return null
  return (
    <div role="status" className="rounded-2xl bg-rose-50 p-4 text-center text-rose-900">
      <p aria-hidden="true" className="motion-safe:animate-bounce text-4xl">
        🎆 ❤️ 🎇
      </p>
      <p className="text-xl font-extrabold">{t('praise.received')}</p>
      {reason && <p>{reason}</p>}
      <button
        type="button"
        className="mt-2 min-h-11 px-4 font-bold underline"
        onClick={() => setShow(false)}
      >
        {t('common.close')}
      </button>
    </div>
  )
}
