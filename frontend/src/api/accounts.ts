import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'

export interface Account {
  id: number
  email: string
  role: string
  member_id: number | null
}

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: () => apiGet<Account[]>('/auth/accounts'),
    retry: false,
  })
}
