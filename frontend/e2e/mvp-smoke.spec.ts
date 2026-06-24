import { expect, test, type Dialog, type Page } from '@playwright/test'

const password = 'Phase10-E2E-Password!'

async function login(page: Page, username: string) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

async function logout(page: Page) {
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/login/)
}

test.describe.serial('MVP phase 10 smoke tests', () => {
  test('administrator publishes general content and a general user can see it', async ({ page }) => {
    await login(page, 'phase10_admin')
    await page.goto('/admin/contents/new')
    await page.getByLabel('标题').fill('E2E 管理员发布通用话术')
    await page.getByLabel('内容类型').selectOption('base_script')
    await page.getByLabel('分类').fill('E2E 发布验证')
    await page.getByLabel('权限级别').selectOption('general')
    await page.getByLabel('摘要').fill('E2E 发布摘要')
    await page.getByLabel('正文').fill('E2E 管理员通过前端创建并发布的通用话术正文。')
    await page.getByRole('button', { name: '保存草稿' }).click()
    await expect(page).toHaveURL(/\/admin\/contents$/)

    const dialogAnswers: Array<string | undefined> = [undefined, 'major', 'E2E 发布摘要']
    const handlePublishDialog = (dialog: Dialog) => dialog.accept(dialogAnswers.shift())
    page.on('dialog', handlePublishDialog)
    const row = page.getByRole('row', { name: /E2E 管理员发布通用话术/ })
    await row.getByRole('button', { name: '发布' }).click()
    await expect(page.getByText(/内容已发布/)).toBeVisible()
    page.off('dialog', handlePublishDialog)

    await logout(page)
    await login(page, 'phase10_general')
    await page.goto('/app/scripts')
    await expect(page.getByText('E2E 管理员发布通用话术')).toBeVisible()
  })

  test('general user cannot see full content in lists, details, AI sources, or quiz', async ({
    page,
  }) => {
    await login(page, 'phase10_general')

    await page.goto('/app/must-reads')
    await expect(page.getByText('E2E 通用最新必读')).toBeVisible()
    await expect(page.getByText('E2E 全量最新必读')).toHaveCount(0)

    await page.goto('/app/scripts')
    await expect(page.getByText('E2E 通用基础话术')).toBeVisible()
    await expect(page.getByText('E2E 全量基础话术')).toHaveCount(0)
    await expect(page.getByText('E2E 全量标准话术')).toHaveCount(0)

    await page.goto('/app/scripts/4')
    await expect(page.getByText('无权查看该内容')).toBeVisible()
    await expect(page.getByText('E2E 全量基础话术')).toHaveCount(0)

    await page.goto('/app/ask?question=客户开场应该怎么说')
    await expect(page.getByRole('heading', { name: '回答' })).toBeVisible()
    await expect(page.getByText(/E2E 通用基础话术/).first()).toBeVisible()
    await expect(page.getByText(/E2E 全量/)).toHaveCount(0)

    await page.goto('/app/quiz')
    await expect(page.getByText(/E2E 通用题目/).first()).toBeVisible()
    await expect(page.getByText(/E2E 全量题目/)).toHaveCount(0)
  })

  test('full user can see both general and full content', async ({ page }) => {
    await login(page, 'phase10_full')

    await page.goto('/app/must-reads')
    await expect(page.getByText('E2E 通用最新必读')).toBeVisible()
    await expect(page.getByText('E2E 全量最新必读')).toBeVisible()

    await page.goto('/app/scripts')
    await expect(page.getByText('E2E 通用基础话术')).toBeVisible()
    await expect(page.getByText('E2E 全量基础话术')).toBeVisible()
    await expect(page.getByText('E2E 通用标准话术')).toBeVisible()
    await expect(page.getByText('E2E 全量标准话术')).toBeVisible()

    await page.goto('/app/quiz')
    await expect(page.getByText(/E2E 通用题目/).first()).toBeVisible()
    await expect(page.getByText(/E2E 全量题目/)).toBeVisible()

    await page.goto('/app/ask?question=完整权限员工可以使用哪些口径')
    await expect(page.getByRole('heading', { name: '回答' })).toBeVisible()
    await expect(page.getByText(/E2E 全量/).first()).toBeVisible()
  })

  test('AI miss shows the fixed response and appears in the admin list', async ({ page }) => {
    const missedQuestion = 'E2E_MISS_这是一个确定性未命中问题'
    await login(page, 'phase10_general')
    await page.goto(`/app/ask?question=${encodeURIComponent(missedQuestion)}`)
    await expect(page.getByText('当前没有有效标准口径，请联系管理员。')).toBeVisible()

    await logout(page)
    await login(page, 'phase10_admin')
    await page.goto('/admin/missed-questions')
    await expect(page.getByText(missedQuestion)).toBeVisible()
  })

  test('quiz results are immediate and are not persisted after reload', async ({ page }) => {
    await login(page, 'phase10_general')
    await page.goto('/app/quiz')

    const cards = page.locator('.quiz-card')
    await expect(cards).toHaveCount(5)
    for (let index = 0; index < 5; index += 1) {
      await cards.nth(index).locator('input[type="radio"]').first().check()
    }
    await page.getByRole('button', { name: '提交答案' }).click()
    await expect(page.getByText(/回答正确|回答错误/).first()).toBeVisible()
    await expect(page.getByText(/E2E 通用题目解析/).first()).toBeVisible()

    await page.reload()
    await expect(page.getByText(/回答正确|回答错误/)).toHaveCount(0)
    await expect(page.getByText(/分数历史|答题历史|排行|个人统计/)).toHaveCount(0)
  })
})
