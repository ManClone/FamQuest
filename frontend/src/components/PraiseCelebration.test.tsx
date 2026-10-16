import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it } from 'vitest'
import i18n from '../i18n'
import { PraiseCelebration } from './PraiseCelebration'

beforeEach(async () => {
  localStorage.clear()
  await i18n.changeLanguage('en')
})

it('celebrates new praise once without replaying old praise on reload', async () => {
  const view = render(<PraiseCelebration memberId={1} latestId={0} />)
  expect(screen.queryByRole('status')).toBeNull()
  view.rerender(<PraiseCelebration memberId={1} latestId={1} reason="Great help" />)
  expect(await screen.findByText('You received praise!')).toBeVisible()
  expect(screen.getByText('Great help')).toBeVisible()
  view.unmount()
  render(<PraiseCelebration memberId={1} latestId={1} reason="Great help" />)
  expect(screen.queryByRole('status')).toBeNull()
})
