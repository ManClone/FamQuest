import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import WandIcon from '~icons/fluent-emoji-flat/sparkles'
import PencilIcon from '~icons/lucide/pencil'
import PlusIcon from '~icons/lucide/plus'

import {
  CHORES_KEY,
  type Chore,
  type ChorePlan,
  type ChoreRoom,
  choreData,
  updateChore,
  useChoresMutation,
  useApproveChoreCredit,
  useWeeklyChorePreview,
  useConfirmedWeeklyChores,
  usePublishWeeklyChores,
  type WeeklyChorePreview,
} from '../../api/chores'
import { useMembers } from '../../api/members'
import { LEVEL_COLORS, byUrgency, intervalText, statusText } from '../../chores'
import { TaskIcon } from '../../components/TaskIcon'
import { Alert, Button, Section, Switch } from '../../components/ui'
import { errorMessage } from '../../errors'

interface ChoresSectionProps {
  plan: ChorePlan | undefined
  error: unknown
  onWizard: () => void
  onAddRoom: () => void
  onEditRoom: (room: ChoreRoom) => void
  onAddChore: (room: ChoreRoom) => void
  onEditChore: (chore: Chore) => void
}

/** Putzplan verwalten: Räume mit ihren Aufgaben und Abständen; der Assistent schlägt beides vor. */
export function ChoresSection({
  plan,
  error,
  onWizard,
  onAddRoom,
  onEditRoom,
  onAddChore,
  onEditChore,
}: ChoresSectionProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const members = useMembers()
  const adults = (members.data ?? []).filter((member) => member.role === 'parent')
  const approve = useApproveChoreCredit()
  const [showWeeklyPreview, setShowWeeklyPreview] = useState(false)
  const weeklyPreview = useWeeklyChorePreview(showWeeklyPreview)
  const confirmedWeek = useConfirmedWeeklyChores(showWeeklyPreview)
  const publishWeek = usePublishWeeklyChores()
  const [weeklyEdits, setWeeklyEdits] = useState<Record<number, number>>({})
  const [weekPublished, setWeekPublished] = useState(false)
  const [selectedMembers, setSelectedMembers] = useState<Record<number, number>>({})
  const toggleActive = useChoresMutation((chore: Chore) =>
    updateChore(chore.id, { ...choreData(chore), active: !chore.active }),
  )
  const rooms = plan?.rooms ?? []

  return (
    <>
      <Section title={t('chores.section')}>
        {error ? <Alert>{errorMessage(t, error)}</Alert> : null}
        {toggleActive.isError && <Alert>{errorMessage(t, toggleActive.error)}</Alert>}
        {approve.isError && <Alert>{errorMessage(t, approve.error)}</Alert>}
        <p className="text-lg text-slate-600">
          {t(rooms.length === 0 ? 'chores.section_empty' : 'chores.section_intro')}
        </p>
        <div className="flex flex-wrap gap-3">
          <Button onClick={onWizard} disabled={plan === undefined}>
            <WandIcon className="size-7" aria-hidden="true" />
            {t('chores.wizard_start')}
          </Button>
          <Button variant="secondary" onClick={onAddRoom} disabled={plan === undefined}>
            <PlusIcon className="size-6" aria-hidden="true" />
            {t('chores.add_room')}
          </Button>
        </div>
      </Section>

      <Section title="Wochenverteilung für Erwachsene">
        <p className="text-base text-slate-600">
          Vorschlag für die laufende Woche. Feste Aufgaben bleiben zugeordnet; andere werden
          nach geschätzter Arbeitszeit verteilt. Erst mit „Wochenplan verbindlich übernehmen“
          wird die Verteilung für alle im Putzplan sichtbar.
        </p>
        <div className="mt-3">
          <Button
            variant="secondary"
            onClick={() => setShowWeeklyPreview((previous) => !previous)}
            disabled={plan === undefined}
          >
            {showWeeklyPreview ? 'Vorschau ausblenden' : 'Wochenvorschlag anzeigen'}
          </Button>
        </div>
        {showWeeklyPreview && (
          <div className="mt-4">
            {weeklyPreview.isPending && <p>Wochenvorschlag wird geladen …</p>}
            {weeklyPreview.isError && <Alert>{errorMessage(t, weeklyPreview.error)}</Alert>}
            {publishWeek.isError && <Alert>{errorMessage(t, publishWeek.error)}</Alert>}
            {confirmedWeek.data && confirmedWeek.data.assignments.length > 0 && (
              <p className="font-semibold text-green-700">
                Für diese Woche ist bereits ein Plan bestätigt.
              </p>
            )}
            {weekPublished && <p className="font-semibold text-green-700">Wochenplan gespeichert.</p>}
            {weeklyPreview.data && (
              <>
                <p className="font-semibold text-slate-700">
                  Woche ab {weeklyPreview.data.week_start}
                </p>
                {weeklyPreview.data.assignments.length === 0 ? (
                  <p className="mt-2 text-slate-600">Keine Aufgaben für diese Woche vorgeschlagen.</p>
                ) : (
                  <>
                    <ul className="mt-3 flex flex-col gap-3">
                      {weeklyPreview.data.assignments.map((assignment) => {
                        const chore = plan?.chores.find((item) => item.id === assignment.chore_id)
                        const isFixed = chore?.assignment_mode === 'fixed'
                        const assigned = weeklyEdits[assignment.chore_id]
                          ?? confirmedWeek.data?.assignments.find(
                            (item) => item.chore_id === assignment.chore_id,
                          )?.member_id
                          ?? assignment.member_id
                        return (
                          <li key={assignment.chore_id} className="rounded-xl border border-slate-200 p-3">
                            <label className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-bold text-slate-800">
                                {chore?.title ?? `Aufgabe #${assignment.chore_id}`}
                              </span>
                              <select
                                aria-label={`Zuständig für ${chore?.title ?? assignment.chore_id}`}
                                value={assigned}
                                disabled={isFixed || publishWeek.isPending}
                                onChange={(event) => {
                                  setWeeklyEdits((old) => ({
                                    ...old,
                                    [assignment.chore_id]: Number(event.target.value),
                                  }))
                                  setWeekPublished(false)
                                }}
                                className="rounded-lg border border-slate-300 p-2"
                              >
                                {adults.map((member) => (
                                  <option key={member.id} value={member.id}>{member.name}</option>
                                ))}
                              </select>
                            </label>
                            <p className="text-sm text-slate-600">
                              {assignment.estimated_minutes} Minuten · {assignment.adult_xp} XP
                              {isFixed ? ' · Fest zugeordnet' : ''}
                            </p>
                          </li>
                        )
                      })}
                    </ul>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        disabled={publishWeek.isPending || confirmedWeek.isPending}
                        onClick={() => {
                          const assignments: WeeklyChorePreview['assignments'] =
                            weeklyPreview.data.assignments.map((entry) => ({
                              ...entry,
                              member_id: weeklyEdits[entry.chore_id]
                                ?? confirmedWeek.data?.assignments.find(
                                  (saved) => saved.chore_id === entry.chore_id,
                                )?.member_id
                                ?? entry.member_id,
                            }))
                          publishWeek.mutate(assignments, {
                            onSuccess: () => {
                              setWeekPublished(true)
                              setWeeklyEdits({})
                              void queryClient.invalidateQueries({ queryKey: CHORES_KEY })
                            },
                          })
                        }}
                      >
                        {publishWeek.isPending ? 'Speichert …' : 'Wochenplan verbindlich übernehmen'}
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setWeeklyEdits({})
                          setWeekPublished(false)
                        }}
                      >
                        Änderungen verwerfen
                      </Button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        )}
      </Section>

      {rooms.map((room) => {
        const chores = (plan?.chores ?? [])
          .filter((chore) => chore.room_id === room.id)
          .sort((a, b) => a.interval_days - b.interval_days || byUrgency(a, b))
        return (
          <Section key={room.id} title={room.name}>
            {chores.length === 0 && (
              <p className="text-lg text-slate-600">{t('chores.room_empty')}</p>
            )}
            {chores.length > 0 && (
              <ul className="flex flex-col gap-3">
                {chores.map((chore) => (
                  <li
                    key={chore.id}
                    className={`flex items-center gap-3 rounded-2xl border-2 border-slate-100 p-2 sm:p-3 ${chore.active ? '' : 'bg-slate-50'}`}
                  >
                    <button
                      type="button"
                      onClick={() => onEditChore(chore)}
                      aria-label={t('chores.edit_title', { title: chore.title })}
                      className="flex min-w-0 flex-1 items-center gap-4 rounded-xl p-1 text-left transition-colors hover:bg-orange-50 focus-visible:outline-4 focus-visible:outline-orange-400 active:bg-orange-100"
                    >
                      <TaskIcon
                        icon={chore.icon}
                        className={`size-14 ${chore.active ? '' : 'opacity-40'}`}
                      />
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="text-lg font-bold break-words text-slate-800">
                          {chore.title}
                          {!chore.active && (
                            <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-sm font-bold text-slate-600">
                              {t('chores.paused')}
                            </span>
                          )}
                        </span>
                        <span className="text-base text-slate-600">
                          {intervalText(t, chore.interval_days)}
                        </span>
                      </span>
                      {chore.active && (
                        <span
                          className={`shrink-0 text-right text-base font-bold ${chore.done_today ? 'text-slate-500' : LEVEL_COLORS[chore.level].text}`}
                        >
                          {statusText(t, chore)}
                        </span>
                      )}
                    </button>
                    {chore.done_today && chore.adult_xp > 0 && adults.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <label className="text-sm font-semibold text-slate-700">
                          XP für
                          <select
                            aria-label={`XP-Empfänger für ${chore.title}`}
                            value={selectedMembers[chore.id] ?? chore.done_by ?? ''}
                            onChange={(event) => setSelectedMembers((previous) => ({
                              ...previous, [chore.id]: Number(event.target.value),
                            }))}
                            className="ml-2 rounded-lg border border-slate-300 p-2"
                          >
                            <option value="">Person wählen</option>
                            {adults.map((member) => (
                              <option key={member.id} value={member.id}>{member.name}</option>
                            ))}
                          </select>
                        </label>
                        <Button
                          variant="secondary"
                          disabled={approve.isPending || !(
                            selectedMembers[chore.id] ?? chore.done_by
                          )}
                          onClick={() => approve.mutate({
                            id: chore.id,
                            memberId: selectedMembers[chore.id] ?? chore.done_by!,
                          })}
                        >
                          {chore.adult_xp} XP freigeben
                        </Button>
                      </div>
                    )}
                    <Switch
                      checked={chore.active}
                      onChange={() => toggleActive.mutate(chore)}
                      disabled={toggleActive.isPending && toggleActive.variables?.id === chore.id}
                      label={t('chores.active_toggle', { title: chore.title })}
                    />
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => onAddChore(room)}>
                <PlusIcon className="size-6" aria-hidden="true" />
                {t('chores.add_chore')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => onEditRoom(room)}
                aria-label={t('chores.edit_room', { name: room.name })}
              >
                <PencilIcon className="size-6" aria-hidden="true" />
                {t('chores.edit_room_short')}
              </Button>
            </div>
          </Section>
        )
      })}
    </>
  )
}
