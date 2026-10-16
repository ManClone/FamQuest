import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it } from 'vitest'
import i18n from '../i18n'
import { PraiseCelebration } from './PraiseCelebration'

beforeEach(async () => {
  localStorage.clear()
  await i18n.changeLanguage('en')
})

it('celebrates new praise once without replaying old praise on reload', async () => {
  const view = render(<PraiseCelebration memberId={1} latestId={0} />)
  expect(screen.queryByRole('dialog')).toBeNull()
  view.rerender(<PraiseCelebration memberId={1} latestId={1} reason="Great help" />)
  expect(await screen.findByText('You received praise!')).toBeVisible()
  expect(screen.getByText('Great help')).toBeVisible()
  view.unmount()
  render(<PraiseCelebration memberId={1} latestId={1} reason="Great help" />)
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('shows manual deductions with the reason and amount, then closes without replay', async () => {
  const view = render(<PraiseCelebration memberId={1} latestId={0} deductionId={0} />)
  view.rerender(
    <PraiseCelebration
      memberId={1}
      latestId={0}
      deductionId={3}
      deductionAmount={2}
      deductionReason="Agreed correction"
    />,
  )
  const dialog = await screen.findByRole('dialog', { name: 'Stars deducted' })
  expect(dialog).toHaveTextContent('−2')
  expect(dialog).toHaveTextContent('Agreed correction')
  expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
  view.unmount()
  render(<PraiseCelebration memberId={1} latestId={0} deductionId={3} deductionAmount={2} />)
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('queues praise and deductions rather than putting two overlays on top of each other', async () => {
  const view = render(<PraiseCelebration memberId={1} latestId={0} deductionId={0} />)
  view.rerender(
    <PraiseCelebration
      memberId={1}
      latestId={1}
      reason="Great help"
      deductionId={2}
      deductionAmount={1}
      deductionReason="Correction"
    />,
  )
  expect(await screen.findByRole('dialog', { name: 'You received praise!' })).toBeVisible()
  expect(screen.getAllByRole('dialog')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(await screen.findByRole('dialog', { name: 'Stars deducted' })).toBeVisible()
})
