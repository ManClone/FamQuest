import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { makeMember, mockApi } from '../../test/utils'
import { ConfirmedChores } from './ConfirmedChores'

afterEach(() => vi.unstubAllGlobals())

it('loads confirmed household executions on demand and removes only the selected execution after confirmation', async () => {
  await i18n.changeLanguage('en')
  const user = userEvent.setup()
  let items = [11, 12, 13, 14].map((id) => ({
    id,
    source: 'chore',
    task_id: 7,
    member_id: 1,
    title: 'Litter box',
    icon: 'fluent-emoji-flat:cat',
    points: 4,
    date: '2026-10-16',
    completed_at: `2026-10-16T10:00:${id}Z`,
  }))
  const calls = mockApi({
    'GET /api/chore-approvals/confirmed': () => Response.json({ items, has_more: false }),
    'DELETE /api/chore-approvals/12/confirmed': () => {
      items = items.filter((item) => item.id !== 12)
      return new Response(null, { status: 204 })
    },
  })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ConfirmedChores members={[makeMember({ id: 1, name: 'Tim' })]} />
    </QueryClientProvider>,
  )
  expect(calls).toHaveLength(0)
  await user.click(screen.getByText('Confirmed household tasks'))
  expect(await screen.findAllByText('Litter box')).toHaveLength(4)
  const region = screen.getByRole('region', { name: 'Confirmed household tasks' })
  expect(region.className).toContain('overflow-y-auto')
  expect(region.className).toContain('max-h-')
  expect(region.closest('details')?.className).toContain('bg-white')
  const row = screen.getAllByRole('listitem')[1]
  await user.click(within(row).getByRole('button', { name: /^Undo$/ }))
  expect(calls.some((call) => call.key.startsWith('DELETE'))).toBe(false)
  await user.click(within(row).getByRole('button', { name: 'Yes, undo' }))
  await waitFor(() => expect(screen.getAllByText('Litter box')).toHaveLength(3))
  expect(calls.filter((call) => call.key.startsWith('DELETE')).map((call) => call.key)).toEqual([
    'DELETE /api/chore-approvals/12/confirmed',
  ])
})
