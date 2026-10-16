import { useQuery } from '@tanstack/react-query'

import { api, apiGet } from './client'
import { useParentMutation } from './mutations'
import { POINTS_KEY } from './points'
import { TODAY_KEY } from './today'

/** Erledigung, die auf die Kontrolle der Eltern wartet. */
export interface Approval {
  source?: 'task' | 'chore'
  id: number
  task_id: number
  title: string
  icon: string
  points: number
  member_id: number
  /** Tag der Erledigung (`YYYY-MM-DD`). */
  date: string
  completed_at: string
}

export const APPROVALS_KEY = ['approvals'] as const

export function useApprovals() {
  return useQuery({ queryKey: APPROVALS_KEY, queryFn: () => apiGet<Approval[]>('/approvals') })
}

export const approve = (item: number | Approval) =>
  api<void>(
    'POST',
    typeof item === 'number'
      ? `/approvals/${item}`
      : `/${item.source === 'chore' ? 'chore-approvals' : 'approvals'}/${item.id}`,
  )
export const reject = (item: number | Approval) =>
  api<void>(
    'DELETE',
    typeof item === 'number'
      ? `/approvals/${item}`
      : `/${item.source === 'chore' ? 'chore-approvals' : 'approvals'}/${item.id}`,
  )

/** Bestätigen oder ablehnen; lädt danach Kontrollen, Familienansicht und Punkte neu. */
export function useApprovalMutation<TVariables>(request: (variables: TVariables) => Promise<void>) {
  return useParentMutation(request, [
    APPROVALS_KEY,
    TODAY_KEY,
    POINTS_KEY,
    ['member-progress'],
    ['chores'],
    ['my-chores'],
  ])
}
