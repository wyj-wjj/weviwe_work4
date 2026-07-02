import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import MustReadDetailPage from '../src/pages/app/MustReadDetailPage.vue'
import MustReadListPage from '../src/pages/app/MustReadListPage.vue'
import ScriptDetailPage from '../src/pages/app/ScriptDetailPage.vue'
import ScriptsPage from '../src/pages/app/ScriptsPage.vue'
import { createAppRouter } from '../src/router'
import { useAuthStore, type AuthUser } from '../src/stores/auth'
import { getMustRead, getScript, listMustReads, listScripts } from '../src/api/content'

vi.mock('../src/api/content', () => ({
  getMustRead: vi.fn(),
  getScript: vi.fn(),
  listMustReads: vi.fn(),
  listScripts: vi.fn(),
}))

const mockedListMustReads = vi.mocked(listMustReads)
const mockedGetMustRead = vi.mocked(getMustRead)
const mockedListScripts = vi.mocked(listScripts)
const mockedGetScript = vi.mocked(getScript)

const employeeUser: AuthUser = {
  id: 2,
  username: 'general',
  display_name: '通用员工',
  account_type: 'general_user',
  content_level: 'general',
}

async function renderAppPage(component: object, path = '/app') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  const auth = useAuthStore()
  auth.setSession('token', employeeUser)
  await router.push(path)
  await router.isReady()

  return render(component, {
    global: {
      plugins: [pinia, router],
    },
  })
}

beforeEach(() => {
  sessionStorage.clear()
  mockedListMustReads.mockReset()
  mockedGetMustRead.mockReset()
  mockedListScripts.mockReset()
  mockedGetScript.mockReset()
})

test('must-read list renders title, published time, effective time, and permission level', async () => {
  mockedListMustReads.mockResolvedValue({
    items: [
      {
        id: 11,
        title: '产品口径更新',
        category: '公告',
        published_at: '2026-06-17T09:00:00',
        effective_at: '2026-06-18T00:00:00',
        permission_level: 'general',
        update_level: 'medium',
        update_body: '新版介绍口径',
        adjustment_points: ['突出稳定性'],
      },
    ],
  })

  const { getByText } = await renderAppPage(MustReadListPage, '/app/must-reads')

  await waitFor(() => {
    expect(getByText('产品口径更新')).toBeInTheDocument()
  })
  expect(getByText('发布时间：2026-06-17 17:00')).toBeInTheDocument()
  expect(getByText('生效时间：2026-06-18 08:00')).toBeInTheDocument()
  expect(getByText('更新级别：中更新')).toBeInTheDocument()
  expect(getByText('通用级')).toBeInTheDocument()
})

test('must-read list renders the dedicated empty state when no visible content exists', async () => {
  mockedListMustReads.mockResolvedValue({ items: [] })

  const { getByText } = await renderAppPage(MustReadListPage, '/app/must-reads')

  await waitFor(() => {
    expect(getByText('暂无可查看的最新必读')).toBeInTheDocument()
  })
})

test('must-read detail renders body, adjustment points, dates, and permission level', async () => {
  mockedGetMustRead.mockResolvedValue({
    id: 11,
    title: '产品口径更新',
    category: '公告',
    published_at: '2026-06-17T09:00:00',
    effective_at: '2026-06-18T00:00:00',
    permission_level: 'general',
    update_level: 'major',
    update_body: '请使用新版产品介绍口径。',
    adjustment_points: ['新增合规提示', '强调服务边界'],
  })

  const { getByText } = await renderAppPage(MustReadDetailPage, '/app/must-reads/11')

  await waitFor(() => {
    expect(getByText('产品口径更新')).toBeInTheDocument()
  })
  expect(getByText('请使用新版产品介绍口径。')).toBeInTheDocument()
  expect(getByText('新增合规提示')).toBeInTheDocument()
  expect(getByText('强调服务边界')).toBeInTheDocument()
  expect(getByText('发布时间：2026-06-17 17:00')).toBeInTheDocument()
  expect(getByText('生效时间：2026-06-18 08:00')).toBeInTheDocument()
  expect(getByText('更新级别：大更新')).toBeInTheDocument()
  expect(getByText('通用级')).toBeInTheDocument()
})

test('must-read permission errors clear stale content and show no-leak copy', async () => {
  mockedGetMustRead.mockRejectedValue({
    status: 403,
    code: 'forbidden',
    message: 'forbidden',
    details: null,
  })

  const { getByText, queryByText } = await renderAppPage(MustReadDetailPage, '/app/must-reads/99')

  await waitFor(() => {
    expect(getByText('无权查看该内容')).toBeInTheDocument()
  })
  expect(queryByText('产品口径更新')).not.toBeInTheDocument()
})

test('scripts page renders base scripts, standard scripts, and filters by category', async () => {
  mockedListScripts
    .mockResolvedValueOnce({
      base_scripts: [
        {
          id: 21,
          content_type: 'base_script',
          title: '基础开场白',
          category: '开户',
          permission_level: 'general',
          update_level: 'minor',
          updated_at: '2026-06-17T10:00:00',
          summary_points: ['先确认客户身份', '说明服务范围'],
        },
      ],
      standard_scripts: [
        {
          id: 22,
          content_type: 'standard_script',
          title: '风险提示',
          category: '风控',
          permission_level: 'general',
          update_level: 'medium',
          updated_at: '2026-06-17T11:00:00',
          scene: '高风险咨询',
          recommended_speech_summary: '建议先说明风险等级和适用边界。',
        },
      ],
    })
    .mockResolvedValueOnce({
      base_scripts: [],
      standard_scripts: [
        {
          id: 22,
          content_type: 'standard_script',
          title: '风险提示',
          category: '风控',
          permission_level: 'general',
          update_level: 'medium',
          updated_at: '2026-06-17T11:00:00',
          scene: '高风险咨询',
          recommended_speech_summary: '建议先说明风险等级和适用边界。',
        },
      ],
    })

  const { getByLabelText, getByText, queryByText } = await renderAppPage(ScriptsPage, '/app/scripts')

  await waitFor(() => {
    expect(getByText('基础开场白')).toBeInTheDocument()
  })
  expect(getByText('先确认客户身份')).toBeInTheDocument()
  expect(getByText('说明服务范围')).toBeInTheDocument()
  expect(getByText('更新时间：2026-06-17 18:00')).toBeInTheDocument()
  expect(getByText('更新级别：小更新')).toBeInTheDocument()
  expect(getByText('高风险咨询')).toBeInTheDocument()
  expect(getByText('建议先说明风险等级和适用边界。')).toBeInTheDocument()

  await fireEvent.update(getByLabelText('场景分类'), '风控')

  await waitFor(() => {
    expect(mockedListScripts).toHaveBeenLastCalledWith({ category: '风控' })
  })
  expect(queryByText('基础开场白')).not.toBeInTheDocument()
})

test('standard script detail renders speech fields and copies rendered text', async () => {
  const originalClipboard = navigator.clipboard
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
  mockedGetScript.mockResolvedValue({
    id: 22,
    title: '风险提示',
    content_type: 'standard_script',
    category: '风控',
    permission_level: 'general',
    update_level: 'medium',
    scene: '高风险咨询',
    recommended_speech: '建议先说明风险等级。',
    forbidden_speech: '不能承诺收益。',
    notes: '必要时转交主管。',
    updated_at: '2026-06-17T11:00:00',
    copy_text: '高风险咨询\n建议先说明风险等级。\n不能承诺收益。\n必要时转交主管。',
  })

  const { getByRole, getByText } = await renderAppPage(ScriptDetailPage, '/app/scripts/22')

  await waitFor(() => {
    expect(getByText('高风险咨询')).toBeInTheDocument()
  })
  expect(getByText('建议先说明风险等级。')).toBeInTheDocument()
  expect(getByText('不能承诺收益。')).toBeInTheDocument()
  expect(getByText('必要时转交主管。')).toBeInTheDocument()
  expect(getByText('建议先说明风险等级。')).toHaveClass('preserved-text')
  expect(getByText('不能承诺收益。')).toHaveClass('preserved-text')
  expect(getByText('必要时转交主管。')).toHaveClass('preserved-text')
  expect(getByText('更新时间：2026-06-17 19:00')).toBeInTheDocument()
  expect(getByText('更新级别：中更新')).toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '复制推荐说法' }))
  expect(writeText).toHaveBeenCalledWith('建议先说明风险等级。')

  await fireEvent.click(getByRole('button', { name: '复制完整条目' }))
  expect(writeText).toHaveBeenCalledWith(
    '高风险咨询\n建议先说明风险等级。\n不能承诺收益。\n必要时转交主管。',
  )

  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: originalClipboard,
  })
})

test('script detail preserves imported paragraph breaks after publish', async () => {
  mockedGetScript.mockResolvedValue({
    id: 94,
    title: '纬景Token电池基本话术介绍（初稿）',
    content_type: 'base_script',
    category: '产品介绍',
    permission_level: 'general',
    update_level: 'major',
    summary_points: ['AI时代，电力确定性'],
    body: '第一部分：AI时代，电力确定性\n\n1.1 AI市场爆发\n正文第一段。\n\n1.2 AIDC基建热潮\n正文第二段。',
    updated_at: '2026-07-02T01:11:00',
    copy_text:
      '第一部分：AI时代，电力确定性\n\n1.1 AI市场爆发\n正文第一段。\n\n1.2 AIDC基建热潮\n正文第二段。',
  })

  const { getByText } = await renderAppPage(ScriptDetailPage, '/app/scripts/94')

  await waitFor(() => {
    expect(getByText('纬景Token电池基本话术介绍（初稿）')).toBeInTheDocument()
  })
  const body = getByText((content) => content.includes('1.1 AI市场爆发'))
  expect(body).toHaveClass('preserved-text')
})
