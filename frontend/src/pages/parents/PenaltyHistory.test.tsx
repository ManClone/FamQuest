import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { mockApi } from '../../test/utils'
import { PenaltyHistory } from './PenaltyHistory'

afterEach(() => vi.unstubAllGlobals())
it('requires a reversal reason and keeps the original deduction visible', async () => {
  await i18n.changeLanguage('en')
  const user = userEvent.setup()
  let revoked = false
  const calls = mockApi({
    'GET /api/members/1/penalties': () =>
      Response.json({
        penalties: [
          {
            id: 2,
            amount: 4,
            reason: 'Test',
            created_at: '2026-10-16T12:00:00Z',
            reversed_at: revoked ? '2026-10-16T13:00:00Z' : null,
            reversal_reason: revoked ? 'Test entry' : null,
          },
        ],
        has_more: false,
      }),
    'POST /api/members/1/penalties/2/reverse': () => {
      revoked = true
      return Response.json({ id: 2 })
    },
  })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PenaltyHistory memberId={1} />
    </QueryClientProvider>,
  )
  expect(calls).toHaveLength(0)
  await user.click(screen.getByText('Star deduction history'))
  await user.click(await screen.findByRole('button', { name: 'Reverse deduction' }))
  const row = screen.getByRole('listitem')
  expect(within(row).getByRole('button', { name: 'Reverse deduction' })).toBeDisabled()
  await user.type(screen.getByLabelText('Reason for reversal'), 'Test entry')
  await user.click(within(row).getByRole('button', { name: 'Reverse deduction' }))
  await waitFor(() => expect(screen.getByText(/Reversed/)).toHaveTextContent('Test entry'))
  expect(screen.getByText(/−4 ⭐ · Test/)).toBeVisible()
  expect(
    calls.find((call) => call.key === 'POST /api/members/1/penalties/2/reverse')?.body,
  ).toEqual({
    reason: 'Test entry',
    compensation_reviewed: false,
    existing_compensation_id: null,
  })
})

it('requires reviewing possible compensation and links the selected credit', async () => {
  await i18n.changeLanguage('en')
  const user = userEvent.setup()
  const calls = mockApi({
    'GET /api/members/1/penalties': Response.json({
      penalties: [
        {
          id: 47,
          amount: 1,
          reason: 'Test deduction',
          created_at: '2026-10-16T12:00:00Z',
          reversed_at: null,
          reversal_reason: null,
          compensation_candidate_ids: [48],
        },
      ],
      has_more: false,
    }),
    'POST /api/members/1/penalties/47/reverse': Response.json({
      transaction_id: 47,
      refund_transaction_id: 48,
    }),
  })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PenaltyHistory memberId={1} />
    </QueryClientProvider>,
  )
  await user.click(screen.getByText('Star deduction history'))
  await user.click(await screen.findByRole('button', { name: 'Reverse deduction' }))
  await user.type(screen.getByLabelText('Reason for reversal'), 'Already compensated')
  expect(screen.getByRole('button', { name: 'Reverse deduction' })).toBeDisabled()
  await user.selectOptions(screen.getByLabelText('Link an existing compensation (optional)'), '48')
  await user.click(screen.getByRole('button', { name: 'Reverse deduction' }))
  await waitFor(() =>
    expect(calls.find((call) => call.key.startsWith('POST'))?.body).toEqual({
      reason: 'Already compensated',
      compensation_reviewed: false,
      existing_compensation_id: 48,
    }),
  )
})
