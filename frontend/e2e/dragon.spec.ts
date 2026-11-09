/// <reference lib="dom" />
import { expect, test } from '@playwright/test'

// Run this file on its own: e2e/server.sh prepares an empty, isolated database.
test('Sternchen grows into the baby, plays, respects motion settings and falls back safely', async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(180000)
  const password = 'dragon-test-only-123'
  const setup = await request.post('/api/setup', {
    data: {
      language: 'de',
      family_name: 'Drachen-Testfamilie',
      email: 'dragon-parent@example.org',
      password,
      timezone: 'Europe/Berlin',
    },
  })
  expect(setup.status()).toBe(201)
  const me = await setup.json()
  const headers = { 'X-CSRF-Token': me.csrf_token }
  const created = await request.post('/api/members', {
    headers,
    data: {
      name: 'Tim',
      role: 'child',
      color: 'green',
      login: { email: 'dragon-child@example.org', password },
    },
  })
  expect(created.status()).toBe(201)
  const member = await created.json()
  expect(
    (
      await request.put(`/api/members/${member.id}/dragon`, {
        headers,
        data: { name: 'Sternchen' },
      })
    ).status(),
  ).toBe(200)
  const login = await page.request.post('/api/auth/login', {
    data: { email: 'dragon-child@example.org', password },
  })
  expect(login.status()).toBe(200)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sternchen', exact: true })).toBeVisible()
  const iframe = page.locator('iframe[title="Dein Drache in 3D"]')
  await expect(iframe).toHaveAttribute('src', '/dragon3d/index.html?model=egg')
  await expect(page.getByRole('button', { name: 'Spielen', exact: true })).toBeEnabled({
    timeout: 45000,
  })
  const task = await request.post('/api/tasks', {
    headers,
    data: {
      title: 'Testabenteuer',
      icon: 'fluent-emoji-flat:star',
      points: 320,
      time_of_day: null,
      recurrence: { kind: 'daily' },
      member_ids: [member.id],
    },
  })
  expect(task.status()).toBe(201)
  const date = (await (await request.get('/api/today')).json()).date
  expect(
    (
      await request.put(
        `/api/today/tasks/${(await task.json()).id}/members/${member.id}?date=${date}`,
        { headers },
      )
    ).status(),
  ).toBe(204)
  expect(
    (
      await request.post(`/api/members/${member.id}/praise`, {
        headers,
        data: { reason: 'Testlob', request_key: 'd'.repeat(32) },
      })
    ).status(),
  ).toBe(201)
  expect((await (await request.get(`/api/members/${member.id}/progress`)).json()).level).toBe(6)

  const babyResponse = page.waitForResponse(
    (r) => r.url().endsWith('/dragon3d/Baby.glb') && r.status() === 200,
  )
  // Refetch the real progress API while keeping the existing card mounted.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  // React Query's browser focus listener observes visibilitychange.
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(iframe).toHaveAttribute('src', '/dragon3d/index.html?model=baby', { timeout: 65000 })
  await babyResponse
  await expect(page.getByRole('button', { name: 'Spielen', exact: true })).toBeEnabled({
    timeout: 45000,
  })
  const frame = page.frames().find((f) => f.url().includes('dragon3d/index.html'))!
  const status = () =>
    frame.evaluate(async () => {
      // @ts-expect-error Public viewer module is deliberately independent of React/TypeScript.
      const viewer = await import('/dragon3d/viewer.js')
      return viewer.animationStatus()
    })
  await page.getByRole('button', { name: 'Spielen', exact: true }).click()
  await expect.poll(async () => (await status()).motion).toBe('play')
  await frame.locator('canvas').click()
  await expect.poll(async () => (await status()).motion).toBe('play')
  await iframe.scrollIntoViewIfNeeded()
  await page.screenshot({ path: testInfo.outputPath('sternchen-level-6.png') })
  console.log('Before reduced motion', await status())
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect.poll(async () => (await status()).reduced).toBe(true)
  await expect.poll(async () => (await status()).paused).toBe(true)
  const clock = (await status()).lifeClock
  await page.waitForTimeout(200)
  expect((await status()).lifeClock).toBe(clock)
  await page.getByRole('button', { name: 'Spielen', exact: true }).click()
  expect((await status()).paused).toBe(true)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await iframe.scrollIntoViewIfNeeded()
  await expect.poll(async () => (await status()).reduced).toBe(false)
  console.log('After reduced motion', await status())
  await expect.poll(async () => (await status()).paused).toBe(false)
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect.poll(async () => (await status()).paused).toBe(true)
  await page.evaluate(() => {
    delete (document as unknown as Record<string, unknown>).hidden
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect.poll(async () => (await status()).paused).toBe(false)
  const pose = await frame.evaluate(async () => {
    // @ts-expect-error Public viewer module.
    const viewer = await import('/dragon3d/viewer.js')
    return viewer.sampleAnimation('play', 1)
  })
  expect(pose.key).toBe('baby')
  expect(pose.finite).toBe(true)
  expect(errors).toEqual([])

  // Actual WebGL context loss must remove the frame and keep the saved name.
  await frame.locator('canvas').evaluate((canvas) => {
    ;(canvas as HTMLCanvasElement)
      .getContext('webgl2')!
      .getExtension('WEBGL_lose_context')!
      .loseContext()
  })
  await expect(page.getByRole('status').filter({ hasText: 'als Symbol angezeigt' })).toBeVisible()
  await expect(page.locator('iframe')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Sternchen', exact: true })).toBeVisible()

  await page.route('**/dragon3d/Baby.glb', (route) => route.abort())
  await page.reload()
  await expect(page.getByRole('status').filter({ hasText: 'als Symbol angezeigt' })).toBeVisible({
    timeout: 45000,
  })
  await expect(page.locator('iframe')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Sternchen', exact: true })).toBeVisible()
  await page.unroute('**/dragon3d/Baby.glb')
  await page.goto('/tasks')
  await expect(page.getByRole('button', { name: 'Spielen', exact: true })).toBeEnabled({
    timeout: 45000,
  })
  await expect(page.locator('iframe')).toHaveAttribute('src', '/dragon3d/index.html?model=baby')
})
