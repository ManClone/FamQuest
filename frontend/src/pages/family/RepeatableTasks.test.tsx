import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { makeMember, makeTodayTask, mockApi } from '../../test/utils'
import { TaskCard } from './TaskCard'

beforeEach(async () => {
  await i18n.changeLanguage('de')
})
afterEach(() => {
  vi.unstubAllGlobals()
})

it('offers another execution after approval with a new request key', async () => {
  const user = userEvent.setup()
  const member = makeMember()
  const task = makeTodayTask({ title: 'Katzenklo', repeatable: true, needs_approval: true })
  mockApi({
    'GET /api/members': Response.json([member]),
    'PUT /api/today/tasks/1/members/1': new Response(null, { status: 204 }),
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const card = (pending: boolean) => (
    <QueryClientProvider client={client}>
      <TaskCard
        task={{
          ...task,
          done_member_ids: pending ? [1] : [],
          pending_member_ids: pending ? [1] : [],
        }}
        member={member}
        date="2026-10-03"
        size="lg"
      />
    </QueryClientProvider>
  )
  const view = render(card(false))
  await user.click(screen.getByRole('button', { name: /Katzenklo/ }))
  view.rerender(card(true))
  expect(screen.getByTestId('pending-badge')).toBeVisible()
  view.rerender(card(false))
  expect(screen.queryByTestId('pending-badge')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Katzenklo/ }))
  const requests = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'PUT')
  expect(requests).toHaveLength(2)
  const keys = requests.map(([url]) =>
    new URL(String(url), 'http://localhost').searchParams.get('request_key'),
  )
  expect(keys[0]).toMatch(/^[a-f0-9]{32}$/)
  expect(keys[1]).not.toBe(keys[0])
})
