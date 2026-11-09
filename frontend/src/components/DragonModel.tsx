import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

const forms = [
  [1, 'egg'],
  [6, 'baby'],
  [20, 'two'],
  [29, 'three'],
  [36, 'four'],
  [42, 'five'],
  [48, 'bridge'],
  [53, 'six'],
  [58, 'seven'],
  [62, 'eight'],
  [66, 'nine'],
  [70, 'ten'],
] as const

export function DragonModel({ level, onError }: { level: number; onError: () => void }) {
  const model = forms.findLast(([threshold]) => level >= threshold)?.[1] ?? 'egg'
  return <DragonScene key={model} model={model} onError={onError} />
}

function DragonScene({ model, onError }: { model: string; onError: () => void }) {
  const { t } = useTranslation()
  const frame = useRef<HTMLIFrameElement>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const element = frame.current
    if (!element) return
    const send = (message: object) => element.contentWindow?.postMessage(message, location.origin)
    let loaded = false
    let visible = true
    const syncVisibility = () => {
      if (loaded) send({ type: 'dragon-state', model, paused: document.hidden || !visible })
    }
    const timeout = window.setTimeout(onError, 45000)
    const receive = (event: MessageEvent) => {
      if (event.origin !== location.origin || event.source !== element.contentWindow) return
      if (event.data?.type === 'dragon-error') onError()
      if (event.data?.type === 'dragon-ready') {
        loaded = true
        window.clearTimeout(timeout)
        setReady(true)
        syncVisibility()
      }
      if (event.data?.type === 'dragon-tap') {
        send({ type: 'dragon-action', motion: model === 'egg' ? 'heart' : 'play' })
      }
    }
    const observer =
      typeof IntersectionObserver === 'undefined'
        ? undefined
        : new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting
            syncVisibility()
          })
    observer?.observe(element)
    window.addEventListener('message', receive)
    document.addEventListener('visibilitychange', syncVisibility)
    return () => {
      window.clearTimeout(timeout)
      observer?.disconnect()
      window.removeEventListener('message', receive)
      document.removeEventListener('visibilitychange', syncVisibility)
    }
  }, [model, onError])

  return (
    <div className="relative overflow-hidden rounded-2xl bg-indigo-50">
      <iframe
        ref={frame}
        src={`/dragon3d/index.html?model=${model}`}
        title={t('dragon.model_title')}
        onError={onError}
        className="block h-72 w-full border-0 sm:h-80"
        sandbox="allow-scripts allow-same-origin"
      />
      {!ready && (
        <p role="status" className="absolute inset-x-0 top-3 text-center">
          {t('dragon.model_loading')}
        </p>
      )}
      <button
        type="button"
        disabled={!ready}
        className="absolute right-3 bottom-3 rounded-xl bg-white px-3 py-2 font-bold"
        onClick={() =>
          frame.current?.contentWindow?.postMessage(
            { type: 'dragon-action', motion: model === 'egg' ? 'heart' : 'play' },
            location.origin,
          )
        }
      >
        {t('dragon.model_play')}
      </button>
    </div>
  )
}
