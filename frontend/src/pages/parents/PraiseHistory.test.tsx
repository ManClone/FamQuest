import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { mockApi } from '../../test/utils'
import { PraiseHistory } from './PraiseHistory'

afterEach(() => vi.unstubAllGlobals())
it('requires a correction reason and keeps the revoked praise visible in history', async () => {
  await i18n.changeLanguage('en')
  const user = userEvent.setup()
  let revoked = false
  const calls = mockApi({
    'GET /api/members/1/praise': () =>
      Response.json({
        praises: [
          {
            id: 2,
            reason: 'Test',
            created_at: '2026-10-16T12:00:00Z',
            revoked_at: revoked ? '2026-10-16T13:00:00Z' : null,
            revocation_reason: revoked ? 'Test entry' : null,
          },
        ],
        has_more: false,
      }),
    'POST /api/members/1/praise/2/revoke': () => {
      revoked = true
      return Response.json({ id: 2 })
    },
  })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PraiseHistory memberId={1} />
    </QueryClientProvider>,
  )
  expect(calls).toHaveLength(0)
  await user.click(screen.getByText('Praise history'))
  await user.click(await screen.findByRole('button', { name: 'Revoke praise' }))
  const row = screen.getByRole('listitem')
  expect(within(row).getByRole('button', { name: 'Revoke praise' })).toBeDisabled()
  await user.type(screen.getByLabelText('Reason for correction'), 'Test entry')
  await user.click(within(row).getByRole('button', { name: 'Revoke praise' }))
  await waitFor(() => expect(screen.getByText(/Revoked/)).toHaveTextContent('Test entry'))
  expect(screen.getByText(/❤️ Test/)).toBeVisible()
  expect(calls.find((call) => call.key === 'POST /api/members/1/praise/2/revoke')?.body).toEqual({
    reason: 'Test entry',
  })
})
