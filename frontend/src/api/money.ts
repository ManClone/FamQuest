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
    queryFn: () =>
      apiGet<WeeklyAllowanceStatus>(
        `/members/${memberId}/money/weekly-allowance?week_start=${encodeURIComponent(monday)}`,
      ),
    enabled: memberId > 0 && /^\d{4}-\d{2}-\d{2}$/.test(monday),
  })
}

export interface WeeklyAllowanceSettings {
  member_id: number
  weekly_amount_cents: number | null
}

export const allowanceSettingsKey = (memberId: number) => ['money', memberId, 'settings'] as const

export function useWeeklyAllowanceSettings(memberId: number) {
  return useQuery({
    queryKey: allowanceSettingsKey(memberId),
    queryFn: () => apiGet<WeeklyAllowanceSettings>(`/members/${memberId}/money/settings`),
    enabled: memberId > 0,
  })
}

export function useSaveWeeklyAllowanceSettings(memberId: number) {
  return useParentMutation(
    (weekly_amount_cents: number | null) =>
      api<WeeklyAllowanceSettings>('PUT', `/members/${memberId}/money/settings`, {
        weekly_amount_cents,
      }),
    [allowanceSettingsKey(memberId), moneyKey(memberId)],
  )
}

export interface BankBalance {
  account_id: number
  display_name: string
  provider: string
  currency: string
  balance_cents: number | null
  observed_at: string | null
}

export function useBankBalances(memberId: number) {
  return useQuery({
    queryKey: ['money', memberId, 'bank-balances'],
    queryFn: () => apiGet<BankBalance[]>(`/members/${memberId}/money/bank-balances`),
    enabled: memberId > 0,
  })
}

export interface BankTransaction {
  id: number
  account_id: number
  booked_on: string
  value_on: string | null
  amount_cents: number
  currency: string
  description: string
  counterparty: string | null
  balance_after_cents: number | null
}

export function useBankTransactions(memberId: number) {
  return useQuery({
    queryKey: ['money', memberId, 'bank-transactions'],
    queryFn: () =>
      apiGet<BankTransaction[]>(`/members/${memberId}/money/bank-transactions?limit=50`),
    enabled: memberId > 0,
  })
}

export interface AllowancePaymentStatus {
  member_id: number
  week_start: string
  expected_cents: number
  received_cents: number
  missing_cents: number
  bank_connected: boolean
}

export function useAllowancePaymentStatus(memberId: number) {
  return useQuery({
    queryKey: ['money', memberId, 'allowance-payment-status'],
    queryFn: () =>
      apiGet<AllowancePaymentStatus>(`/members/${memberId}/money/allowance-payment-status`),
    enabled: memberId > 0,
    refetchInterval: 60_000,
  })
}
