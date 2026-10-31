import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { mockApi } from '../../test/utils'
import { AllowanceSettings } from './AllowanceSettings'

afterEach(() => vi.unstubAllGlobals())

it('speichert Grundtaschengeld getrennt von Aufgaben und Kritik in ganzen Cent', async () => {
  await i18n.changeLanguage('de')
  const calls = mockApi({
    'GET /api/members/1/money/settings': Response.json({ weekly_amount_cents: null }),
    'PUT /api/members/1/money/settings': Response.json({ weekly_amount_cents: 500 }),
  })
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={query}>
      <AllowanceSettings memberId={1} />
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  await user.click(screen.getByText('Grundtaschengeld einstellen'))
  const input = await screen.findByLabelText('Wöchentliches Grundtaschengeld in Euro')
  await user.clear(input)
  await user.type(input, '5,00')
  const button = screen.getByRole('button', { name: 'Grundtaschengeld speichern' })
  await waitFor(() => expect(button).toBeEnabled())
  await user.click(button)
  await waitFor(() =>
    expect(calls.find((call) => call.key.startsWith('PUT'))?.body).toEqual({
      weekly_amount_cents: 500,
    }),
  )
})
