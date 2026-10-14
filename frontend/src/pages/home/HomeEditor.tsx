import { type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import EyeIcon from '~icons/fluent-emoji-flat/eye'

import { type HomeLayout, TILE_IDS, type Tile } from '../../api/home'
import { Alert, Button } from '../../components/ui'
import { errorMessage } from '../../errors'
import { TILES } from './tileMeta'

/**
 * Aufbau der Startseite bearbeiten: Bereiche ein- und ausblenden (die Anordnung ist fest) und
 * wählen, ob die Woche mit heute oder mit Montag beginnt. Darunter zeigt die Seite sofort, wie es
 * aussieht; gespeichert wird erst mit „Speichern“.
 */
export function HomeEditor({
  layout,
  onChange,
  onSave,
  onReset,
  onCancel,
  busy,
  error,
}: {
  layout: HomeLayout
  onChange: (layout: HomeLayout) => void
  onSave: () => void
  onReset: () => void
  onCancel: () => void
  busy: boolean
  error: unknown
}) {
  const { t } = useTranslation()

  const { tiles } = layout
  const toggle = (id: Tile['id']) =>
    onChange({
      ...layout,
      tiles: tiles.map((tile) => (tile.id === id ? { ...tile, visible: !tile.visible } : tile)),
    })
  // In der Reihenfolge, in der die Bereiche auf der Seite stehen.
  const ordered = tiles
    .filter((tile) => tile.id !== 'shopping' && tile.id !== 'events' && tile.id !== 'meals')
    .sort((a, b) => TILE_IDS.indexOf(a.id) - TILE_IDS.indexOf(b.id))

  return (
    <section
      aria-labelledby="home-editor-title"
      className="flex flex-col gap-4 rounded-3xl bg-white p-4 shadow-md ring-4 ring-orange-300"
    >
      <h2 id="home-editor-title" className="text-2xl font-extrabold text-slate-800">
        {t('home.customize')}
      </h2>
      <p className="text-lg text-slate-600">{t('home.customize_hint')}</p>
      {error != null && <Alert>{errorMessage(t, error)}</Alert>}
      {/* Auf dem Wanddisplay zwei Spalten (erst links von oben nach unten, dann rechts), damit die
          Vorschau darunter sichtbar bleibt. */}
      <ol
        className="grid grid-cols-1 gap-2 lg:grid-flow-col lg:grid-cols-2 lg:grid-rows-(--editor-rows)"
        style={{ '--editor-rows': `repeat(${Math.ceil(ordered.length / 2)}, auto)` } as CSSProperties}
      >
        {ordered.map((tile) => {
          const { title, icon: Icon } = TILES[tile.id]
          const name = t(title)
          return (
            <li
              key={tile.id}
              className={`flex flex-wrap items-center gap-3 rounded-2xl p-2 ${tile.visible ? 'bg-orange-50' : 'bg-slate-100'}`}
            >
              <span className="flex min-w-40 flex-1 items-center gap-3">
                <Icon
                  className={`size-10 shrink-0 ${tile.visible ? '' : 'opacity-40 grayscale'}`}
                  aria-hidden="true"
                />
                <span
                  className={`min-w-0 flex-1 truncate text-xl font-bold ${tile.visible ? 'text-slate-800' : 'text-slate-400 line-through'}`}
                >
                  {name}
                </span>
              </span>
              <span className="ml-auto flex items-center gap-3">
                <button
                  type="button"
                  role="switch"
                  aria-checked={tile.visible}
                  aria-label={t('home.tile_visible', { name })}
                  title={t('home.tile_visible', { name })}
                  onClick={() => toggle(tile.id)}
                  className={`flex h-14 w-24 shrink-0 items-center rounded-full p-1 transition-colors focus-visible:outline-4 focus-visible:outline-orange-400 ${tile.visible ? 'justify-end bg-emerald-500' : 'justify-start bg-slate-300'}`}
                >
                  <span className="flex size-12 items-center justify-center rounded-full bg-white shadow">
                    <EyeIcon
                      className={`size-8 ${tile.visible ? '' : 'opacity-30 grayscale'}`}
                      aria-hidden="true"
                    />
                  </span>
                </button>
              </span>
            </li>
          )
        })}
      </ol>
      <div className="flex flex-wrap gap-3">
        <Button onClick={onSave} disabled={busy}>
          {t('actions.save')}
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          {t('actions.cancel')}
        </Button>
        <Button variant="secondary" onClick={onReset} disabled={busy} className="sm:ml-auto">
          {t('home.reset_layout')}
        </Button>
      </div>
    </section>
  )
}
