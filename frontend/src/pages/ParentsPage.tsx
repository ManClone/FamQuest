import { useEffect, useLayoutEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router'
import BackIcon from '~icons/fluent-emoji-flat/left-arrow'

import {
  type Me,
  useLogout,
  useMe,
} from '../api/auth'
import { type Chore, type ChoreRoom, useChores } from '../api/chores'
import { type Member, childrenOf, useMembers } from '../api/members'
import { type Reward, useRewards } from '../api/rewards'
import { type Routine, useRoutines } from '../api/routines'
import { type Task, useTasks } from '../api/tasks'
import { useToday } from '../api/today'
import { Button, Section } from '../components/ui'
import { useIdleTimeout } from '../useIdleTimeout'
import { ApprovalsSection } from './parents/ApprovalsSection'
import { ChoreEditor } from './parents/ChoreEditor'
import { ChoreRoomEditor } from './parents/ChoreRoomEditor'
import { ChoreWizard } from './parents/ChoreWizard'
import { ChoresSection } from './parents/ChoresSection'
import { DeviceSection } from './parents/DeviceSection'
import { AccountsSection, FamilySection } from './parents/FamilySection'
import { MemberEditor } from './parents/MemberEditor'
import { MembersSection } from './parents/MembersSection'
import { PointsEditor } from './parents/PointsEditor'
import { PointsSection } from './parents/PointsSection'
import { PocketMoneySection } from './parents/PocketMoneySection'
import { RewardEditor } from './parents/RewardEditor'
import { RewardPoolPicker } from './parents/RewardPoolPicker'
import { RewardsSection } from './parents/RewardsSection'
import { RoutinesSection } from './parents/RoutinesSection'
import { TaskEditor } from './parents/TaskEditor'
import { TasksSection } from './parents/TasksSection'
import { ParentsNav } from './parents/ParentsNav'
import { PhotosSection } from './parents/PhotosSection'
import { FrameSettingsSection } from './parents/FrameSettingsSection'
import { DEFAULT_AREA, type ParentArea, isParentArea } from './parents/areas'

/** Nach dieser Zeit ohne Eingabe kehrt das Display zur Familienansicht zurück. */
export const PARENT_IDLE_TIMEOUT_MS = 2 * 60 * 1000

export function ParentsPage() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const leave = () => navigate('/')
  useIdleTimeout(PARENT_IDLE_TIMEOUT_MS, leave)

  const { area } = useParams()
  if (area !== undefined && !isParentArea(area)) return <Navigate to="/parents" replace />
  if (!me) return null
  if (me.user.role !== 'admin' && me.user.role !== 'parent') return <Navigate to="/" replace />
  return <ParentSettings me={me} area={area ?? DEFAULT_AREA} onLeave={leave} />
}

function BackButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation()
  return (
    <Button variant="secondary" onClick={onClick} className="self-start">
      <BackIcon className="size-8" aria-hidden="true" />
      {t('parents.back')}
    </Button>
  )
}

function ParentSettings({ me, area, onLeave }: { me: Me; area: ParentArea; onLeave: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const logout = useLogout()
  const members = useMembers()
  const tasks = useTasks()
  const routines = useRoutines()
  const today = useToday()
  const rewards = useRewards()
  const chores = useChores()
  const [editingMember, setEditingMember] = useState<Member | 'new' | null>(null)
  const [editingTask, setEditingTask] = useState<Task | 'new' | null>(null)
  const [pointsMember, setPointsMember] = useState<Member | null>(null)
  const [taskFilter, setTaskFilter] = useState<number | null>(null)
  // Neuer Schritt einer Routine (Editor ohne Personen, Tageszeit und Wiederholung).
  const [newStep, setNewStep] = useState<{ routine: Routine; label: string } | null>(null)
  const [routinesChildId, setRoutinesChildId] = useState<number | null>(null)
  const [rewardsChildId, setRewardsChildId] = useState<number | null>(null)
  const [editingReward, setEditingReward] = useState<{ reward?: Reward; member: Member } | null>(
    null,
  )
  const [poolMember, setPoolMember] = useState<Member | null>(null)
  const [editingChore, setEditingChore] = useState<{ chore?: Chore; roomId: number } | null>(null)
  const [editingRoom, setEditingRoom] = useState<ChoreRoom | 'new' | null>(null)
  const [choreWizard, setChoreWizard] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  // „Kommt wieder“: Aus der Ansicht „Haushalt“ kommt ein Eintrag, der zur Aufgabe im Putzplan wird.
  const comingBackId = area === 'household' ? Number(searchParams.get('todo')) : NaN
  const comingBack = chores.data?.todos.find((todo) => todo.id === comingBackId)
  const firstRoom = chores.data?.rooms[0]

  // Jede Unteransicht (Editor, Vorschläge, Punkte, PIN) beginnt oben, nicht an der Stelle,
  // an der man in der Übersicht gerade war.
  const view = editingMember
    ? 'member'
    : editingTask || newStep
      ? 'task'
      : editingReward
        ? 'reward'
        : poolMember
          ? 'pool'
          : editingChore || (comingBack && firstRoom)
            ? 'chore'
            : editingRoom
              ? 'room'
              : choreWizard
                ? 'wizard'
                : pointsMember
                  ? 'points'
                  : 'overview'
  useLayoutEffect(() => {
    window.scrollTo(0, 0)
  }, [view, area])
  // Rückkehr von der Google-Anmeldung: Ergebnis anzeigen und danach die Adresse aufräumen.
  // Hinweise („… ist gespeichert“) gehören zu dem Bereich, in dem sie entstanden sind.
  const [noticeState, setNoticeState] = useState<{ area: ParentArea; text: string } | null>(null)
  const notice = noticeState?.area === area ? noticeState.text : undefined
  const setNotice = (text: string | undefined) =>
    setNoticeState(text === undefined ? null : { area, text })
  const returnedFromGoogle = searchParams.has('calendar') || searchParams.has('calendar_error')
  useEffect(() => {
    if (returnedFromGoogle) setSearchParams({}, { replace: true })
  }, [returnedFromGoogle, setSearchParams])

  if (editingMember) {
    const closeWith = (message: string) => {
      setEditingMember(null)
      setNotice(message)
    }
    return (
      <MemberEditor
        member={editingMember === 'new' ? undefined : editingMember}
        members={members.data ?? []}
        onSaved={(name) => closeWith(t('members.saved', { name }))}
        onDeleted={(name) => closeWith(t('members.deleted', { name }))}
        onCancel={() => setEditingMember(null)}
      />
    )
  }

  if (editingTask || newStep) {
    const close = () => {
      setEditingTask(null)
      setNewStep(null)
    }
    const closeWith = (message: string) => {
      close()
      setNotice(message)
    }
    return (
      <TaskEditor
        task={editingTask && editingTask !== 'new' ? editingTask : undefined}
        members={childrenOf(members.data ?? [])}
        initialMemberIds={taskFilter === null ? [] : [taskFilter]}
        routineStep={
          newStep
            ? {
                routineId: newStep.routine.id,
                memberId: newStep.routine.member_id,
                time: newStep.routine.time_of_day,
                label: newStep.label,
              }
            : undefined
        }
        timeZone={me.family.timezone}
        onSaved={(title) => closeWith(t('tasks.saved', { title }))}
        onDeleted={(title) => closeWith(t('tasks.deleted', { title }))}
        onCancel={close}
      />
    )
  }

  const childMembers = childrenOf(members.data ?? [])
  const rewardsChild =
    childMembers.find((member) => member.id === rewardsChildId) ?? childMembers[0]
  const routinesChild =
    childMembers.find((member) => member.id === routinesChildId) ?? childMembers[0]

  if (editingReward) {
    const closeWith = (message: string) => {
      setEditingReward(null)
      setNotice(message)
    }
    return (
      <RewardEditor
        reward={editingReward.reward}
        member={editingReward.member}
        onSaved={(name) => closeWith(t('rewards.saved', { name }))}
        onDeleted={(name) => closeWith(t('rewards.deleted', { name }))}
        onCancel={() => setEditingReward(null)}
      />
    )
  }

  if (poolMember) {
    return (
      <RewardPoolPicker
        member={poolMember}
        existing={(rewards.data ?? []).filter((reward) => reward.member_id === poolMember.id)}
        onDone={(count) => {
          setPoolMember(null)
          setNotice(t('rewards.pool_added', { count, name: poolMember.name }))
        }}
        onCancel={() => setPoolMember(null)}
      />
    )
  }

  if (comingBack && firstRoom) {
    const close = (message?: string) => {
      setSearchParams({}, { replace: true })
      setNotice(message)
    }
    return (
      <ChoreEditor
        todo={comingBack}
        roomId={firstRoom.id}
        rooms={chores.data?.rooms ?? []}
        today={chores.data?.date}
        onSaved={(title) => close(t('tasks.saved', { title }))}
        onDeleted={() => close()}
        onCancel={() => close()}
      />
    )
  }

  if (editingChore) {
    const closeWith = (message: string) => {
      setEditingChore(null)
      setNotice(message)
    }
    return (
      <ChoreEditor
        chore={editingChore.chore}
        roomId={editingChore.roomId}
        rooms={chores.data?.rooms ?? []}
        today={chores.data?.date}
        onSaved={(title) => closeWith(t('tasks.saved', { title }))}
        onDeleted={(title) => closeWith(t('tasks.deleted', { title }))}
        onCancel={() => setEditingChore(null)}
      />
    )
  }

  if (editingRoom) {
    const room = editingRoom === 'new' ? undefined : editingRoom
    const closeWith = (message: string) => {
      setEditingRoom(null)
      setNotice(message)
    }
    return (
      <ChoreRoomEditor
        room={room}
        choreCount={
          (chores.data?.chores ?? []).filter((chore) => chore.room_id === room?.id).length
        }
        onSaved={(name) => closeWith(t('chores.room_saved', { name }))}
        onDeleted={(name) => closeWith(t('chores.room_deleted', { name }))}
        onCancel={() => setEditingRoom(null)}
      />
    )
  }

  if (choreWizard && chores.data) {
    return (
      <ChoreWizard
        plan={chores.data}
        hasChildren={childMembers.length > 0}
        onDone={({ chores: count }) => {
          setChoreWizard(false)
          setNotice(t('chores.wizard_added', { count }))
        }}
        onCancel={() => setChoreWizard(false)}
      />
    )
  }

  if (pointsMember) {
    return (
      <PointsEditor
        member={pointsMember}
        timeZone={me.family.timezone}
        onBack={() => setPointsMember(null)}
      />
    )
  }

  return (
    <div className="flex min-h-dvh">
      <ParentsNav area={area} pending={today.data?.pending_approvals ?? 0} />
      <main className="mx-auto flex w-full max-w-3xl min-w-0 flex-col gap-6 p-4 pb-32 sm:p-6 md:pb-6">
        <BackButton onClick={onLeave} />
        <h1 className="text-3xl font-extrabold text-orange-600">{t('parents.title')}</h1>
        {notice && (
          <p
            role="status"
            className="rounded-2xl bg-emerald-100 px-4 py-3 text-lg font-semibold text-emerald-800"
          >
            {notice}
          </p>
        )}

        {area === 'review' && (
          <>
            <ApprovalsSection members={members.data ?? []} today={today.data?.date} />
            <PointsSection
              members={members.data ?? []}
              today={today.data}
              error={today.error}
              onOpen={(member) => {
                setNotice(undefined)
                setPointsMember(member)
              }}
            />
          </>
        )}
        {area === 'family' && (
          <>
            <PocketMoneySection children={childMembers} />
            <MembersSection
              members={members.data}
              error={members.error}
              onEdit={(member) => {
                setNotice(undefined)
                setEditingMember(member)
              }}
              onAdd={() => {
                setNotice(undefined)
                setEditingMember('new')
              }}
            />
          </>
        )}
        {area === 'tasks' && (
          <>
            <TasksSection
              tasks={tasks.data}
              members={childMembers}
              error={tasks.error}
              filter={taskFilter}
              onFilter={setTaskFilter}
              onEdit={(task) => {
                setNotice(undefined)
                setEditingTask(task)
              }}
              onAdd={() => {
                setNotice(undefined)
                setEditingTask('new')
              }}
            />
          </>
        )}
        {area === 'routines' && (
          <>
            <RoutinesSection
              childMembers={childMembers}
              tasks={tasks.data}
              routines={routines.data}
              error={routines.error ?? tasks.error}
              member={routinesChild}
              onSelect={setRoutinesChildId}
              onEditTask={(task) => {
                setNotice(undefined)
                setEditingTask(task)
              }}
              onNewStep={(routine, label) => {
                setNotice(undefined)
                setNewStep({ routine, label })
              }}
              onMessage={setNotice}
            />
          </>
        )}
        {area === 'household' && (
          <>
            {comingBack && !firstRoom && (
              <p
                role="status"
                className="rounded-2xl bg-amber-100 px-4 py-3 text-lg font-semibold text-amber-900"
              >
                {t('todos.need_room', { title: comingBack.title })}
              </p>
            )}
            <ChoresSection
              plan={chores.data}
              error={chores.error}
              onWizard={() => {
                setNotice(undefined)
                setChoreWizard(true)
              }}
              onAddRoom={() => {
                setNotice(undefined)
                setEditingRoom('new')
              }}
              onEditRoom={(room) => {
                setNotice(undefined)
                setEditingRoom(room)
              }}
              onAddChore={(room) => {
                setNotice(undefined)
                setEditingChore({ roomId: room.id })
              }}
              onEditChore={(chore) => {
                setNotice(undefined)
                setEditingChore({ chore, roomId: chore.room_id })
              }}
            />
          </>
        )}
        {area === 'rewards' && (
          <>
            <RewardsSection
              childMembers={childMembers}
              rewards={rewards.data}
              error={rewards.error}
              member={rewardsChild}
              onSelect={setRewardsChildId}
              onEdit={(reward) => {
                const member = childMembers.find((child) => child.id === reward.member_id)
                if (!member) return
                setNotice(undefined)
                setEditingReward({ reward, member })
              }}
              onAdd={(member) => {
                setNotice(undefined)
                setEditingReward({ member })
              }}
              onPickFromPool={(member) => {
                setNotice(undefined)
                setPoolMember(member)
              }}
              timeZone={me.family.timezone}
            />
          </>
        )}
        {area === 'photos' && (
          <>
            <FrameSettingsSection />
            <PhotosSection onMessage={setNotice} />
          </>
        )}
        {area === 'settings' && (
          <>
            <FamilySection me={me} onSaved={setNotice} />
            <DeviceSection />
            <Section title={t('parents.account_section')}>
              <p className="text-lg text-slate-600">
                {t('parents.signed_in_as', { email: me.user.email })}
              </p>
              <Button
                variant="secondary"
                className="self-start"
                disabled={logout.isPending}
                onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
              >
                {t('actions.logout')}
              </Button>
            </Section>
          </>
        )}
      </main>
    </div>
  )
}
