import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { makeChore, makeChorePlan } from '../../test/utils'
import type { ChoreDone } from '../chores/useChoreDone'
import { HouseholdColumn } from './HouseholdColumn'

beforeEach(async () => {
  await i18n.changeLanguage('de')
})

it('repeats a completed family chore separately from undo and reflects its count', async () => {
  const user = userEvent.setup()
  const chore = makeChore({ done_today: true, repeatable: true, completion_count_today: 2 })
  const repeat = vi.fn()
  const toggle = vi.fn()
  const done = { repeat, toggle, busy: false } as unknown as ChoreDone
  const view = (busy: boolean, repeatable = true) => (
    <MemoryRouter>
      <HouseholdColumn
        plan={makeChorePlan({ chores: [{ ...chore, repeatable }] })}
        members={[]}
        done={{ ...done, busy }}
        className="flex"
      />
    </MemoryRouter>
  )
  const rendered = render(view(false))
  const button = screen.getByRole('button', { name: /noch einmal/i })
  await user.click(button)
  expect(repeat).toHaveBeenCalledWith(chore)
  expect(toggle).not.toHaveBeenCalled()
  expect(screen.getByText(/2.*heute|heute.*2/i)).toBeVisible()
  rendered.rerender(view(true))
  expect(screen.getByRole('button', { name: /noch einmal/i })).toBeDisabled()
  rendered.rerender(view(false, false))
  expect(screen.queryByRole('button', { name: /noch einmal/i })).not.toBeInTheDocument()
})
