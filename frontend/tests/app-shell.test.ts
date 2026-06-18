import { render } from '@testing-library/vue'

import AppShell from '../src/components/AppShell.vue'

function renderAtViewport(width: number) {
  window.innerWidth = width
  return render(AppShell, {
    props: {
      area: width < 768 ? 'employee' : 'admin',
    },
    slots: {
      default: '<main data-testid="content">content</main>',
    },
  })
}

test.each([375, 1280])('application shell constrains horizontal overflow at %ipx', (width) => {
  const { getByTestId } = renderAtViewport(width)

  const shell = getByTestId('app-shell')

  expect(shell).toHaveStyle({
    maxWidth: '100vw',
    overflowX: 'hidden',
  })
})
