import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

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

const sendApproval = (item: number | Approval, praise: boolean) =>
  api<void>(
    'POST',
    typeof item === 'number'
      ? `/approvals/${item}${praise ? '?praise=true' : ''}`
      : `/${item.source === 'chore' ? 'chore-approvals' : 'approvals'}/${item.id}${praise ? '?praise=true' : ''}`,
  )
export const approve = (item: number | Approval) => sendApproval(item, false)
export const approveWithPraise = (item: number | Approval) => sendApproval(item, true)

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
    CONFIRMED_CHORES_KEY,
    TODAY_KEY,
    POINTS_KEY,
    ['member-progress'],
    ['chores'],
    ['my-chores'],
  ])
}

export const CONFIRMED_CHORES_KEY = ['confirmed-chores'] as const
export function useConfirmedChores(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: CONFIRMED_CHORES_KEY,
    queryFn: ({ pageParam }) =>
      apiGet<{ items: Approval[]; has_more: boolean }>(
        `/chore-approvals/confirmed${pageParam === null ? '' : `?before=${pageParam}`}`,
      ),
    initialPageParam: null as number | null,
    getNextPageParam: (page) => (page.has_more ? page.items.at(-1)?.id : undefined),
    enabled,
  })
}
export const undoConfirmedChore = (id: number) =>
  api<void>('DELETE', `/chore-approvals/${id}/confirmed`)
