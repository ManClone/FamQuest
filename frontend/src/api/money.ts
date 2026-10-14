import { useQuery } from '@tanstack/react-query'

import { api, apiGet } from './client'
import { useParentMutation } from './mutations'

export interface MoneyOverview {
  member_id: number
  allowance_cents: number
  bonus_cents: number
  total_cents: number
}

export interface WeeklyAllowanceInput {
  amount_cents: number
  /** Monday, YYYY-MM-DD. No automatic booking occurs. */
  week_start: string
}

export interface WeeklyAllowanceResult {
  member_id: number
  week_start: string
  booked: boolean
  allowance_cents: number
}

export const moneyKey = (memberId: number) => ['money', memberId] as const

export function useMoneyOverview(memberId: number) {
  return useQuery({
    queryKey: moneyKey(memberId),
    queryFn: () => apiGet<MoneyOverview>(`/members/${memberId}/money`),
    enabled: memberId > 0,
  })
}

export const creditWeeklyAllowance = (memberId: number, input: WeeklyAllowanceInput) =>
  api<WeeklyAllowanceResult>('POST', `/members/${memberId}/money/weekly-allowance`, input)

export function useCreditWeeklyAllowance(memberId: number) {
  return useParentMutation(
    (input: WeeklyAllowanceInput) => creditWeeklyAllowance(memberId, input),
    [moneyKey(memberId), ['money', memberId, 'weekly-allowance']],
  )
}

export interface WeeklyAllowanceStatus {
  member_id: number
  week_start: string
  booked: boolean
}

export const weeklyAllowanceStatusKey = (memberId: number, monday: string) =>
  ['money', memberId, 'weekly-allowance', monday] as const

export function useWeeklyAllowanceStatus(memberId: number, monday: string) {
  return useQuery({
    queryKey: weeklyAllowanceStatusKey(memberId, monday),
    queryFn: () => apiGet<WeeklyAllowanceStatus>(
      `/members/${memberId}/money/weekly-allowance?week_start=${encodeURIComponent(monday)}`,
    ),
    enabled: memberId > 0 && /^\d{4}-\d{2}-\d{2}$/.test(monday),
  })
}
