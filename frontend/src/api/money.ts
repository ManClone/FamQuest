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
    [moneyKey(memberId)],
  )
}
