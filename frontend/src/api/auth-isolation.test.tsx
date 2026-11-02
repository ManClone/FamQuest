import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'

import { makeMe, mockApi } from '../test/utils'
import { ME_KEY, useLogin, useLogout } from './auth'

afterEach(() => vi.unstubAllGlobals())

function environment() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(['members'], [{ name: 'Previous family' }])
  queryClient.setQueryData(['today'], { secret: 'previous tasks' })
  queryClient.setQueryData(['photos'], { private: true })
  queryClient.setQueryData(ME_KEY, makeMe())
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

it('discards previous family data after a successful new login', async () => {
  localStorage.setItem('famquest-praise-seen-1', '1000')
  localStorage.setItem('famquest-deduction-seen-1', '500')
  localStorage.setItem('famquest.frameIdleMinutes', '5')
  const { queryClient, wrapper } = environment()
  const me = makeMe({
    family: {
      name: 'New family',
      default_language: 'de',
      timezone: 'Europe/Berlin',
      pin_enabled: false,
    },
  })
  mockApi({ 'POST /api/auth/login': Response.json(me) })
  const { result } = renderHook(() => useLogin(), { wrapper })
  await act(async () => {
    await result.current.mutateAsync({ email: 'new@example.invalid', password: 'test-password' })
  })
  expect(queryClient.getQueryData(ME_KEY)).toEqual(me)
  expect(queryClient.getQueryData(['members'])).toBeUndefined()
  expect(queryClient.getQueryData(['today'])).toBeUndefined()
  expect(queryClient.getQueryData(['photos'])).toBeUndefined()
  expect(localStorage.getItem('famquest-praise-seen-1')).toBeNull()
  expect(localStorage.getItem('famquest-deduction-seen-1')).toBeNull()
  expect(localStorage.getItem('famquest.frameIdleMinutes')).toBe('5')
})

it('clears all private query data after logout', async () => {
  const { queryClient, wrapper } = environment()
  mockApi({ 'POST /api/auth/logout': new Response(null, { status: 204 }) })
  const { result } = renderHook(() => useLogout(), { wrapper })
  await act(async () => {
    await result.current.mutateAsync()
  })
  await waitFor(() => expect(queryClient.getQueryCache().getAll()).toHaveLength(0))
})
