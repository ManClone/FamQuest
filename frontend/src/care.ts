import type { ChorePlan } from './api/chores'
import type { Member } from './api/members'

export interface CareSegment {
  member: Member
  /** Geschätzter Zeitaufwand bestätigter, zugeordneter Erledigungen. */
  minutes: number
  /** Kinder werden nach Erledigungen gezeigt, nicht mit Eltern-Minuten verrechnet. */
  count: number
  /** Anteil an allen zugeordneten Erledigungen der Familie. */
  taskPercent: number
  /** Anteil an der Elternzeit; bei vorhandener Zeit zusammen genau 100. */
  percent: number
}

/**
 * Faire Verteilung im Haushalt: wer in den letzten Tagen wie viel vom Putzplan erledigt hat.
 * Erwachsene stehen immer dabei, Kinder nur, wenn sie mitgeholfen haben. Solange niemand etwas
 * angetippt hat, gibt es noch keine Daten (null). Auch eine einzelne Person wird angezeigt.
 */
export function careShares(members: Member[], shares: ChorePlan['shares']): CareSegment[] | null {
  const minutes = (member: Member) =>
    shares.find((share) => share.member_id === member.id)?.estimated_minutes ?? 0
  const count = (member: Member) =>
    shares.find((share) => share.member_id === member.id)?.count ?? 0
  const people = members.filter((member) => member.role === 'parent' || count(member) > 0)
  const parents = people.filter((member) => member.role === 'parent')
  const counts = parents.map(minutes)
  const total = counts.reduce((sum, value) => sum + value, 0)
  const totalCount = people.reduce((sum, member) => sum + count(member), 0)
  if (total === 0 && totalCount === 0) return null

  // Größte Reste zuerst aufrunden, damit die Prozente zusammen 100 ergeben.
  const exact = counts.map((value) => (total > 0 ? (value / total) * 100 : 0))
  const percents = exact.map(Math.floor)
  const order = exact
    .map((value, index) => ({ index, rest: value - Math.floor(value) }))
    .sort((a, b) => b.rest - a.rest)
  const remainder = total > 0 ? 100 - percents.reduce((sum, value) => sum + value, 0) : 0
  for (let i = 0; i < remainder; i++) {
    percents[order[i].index] += 1
  }
  return people.map((member) => ({
    member,
    minutes: minutes(member),
    count: count(member),
    taskPercent: totalCount > 0 ? Math.round((count(member) / totalCount) * 100) : 0,
    percent:
      member.role === 'parent'
        ? percents[parents.findIndex((parent) => parent.id === member.id)]
        : 0,
  }))
}
