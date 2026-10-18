import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from '../App'
import { DEMO_EVALUATION_ACCOUNTS } from '../pages/auth/demoData'

describe('Demo Accounts & Evaluation Flow', () => {
  it('renders all 6 seeded evaluation personas with scope and key test guidance', async () => {
    window.history.replaceState({}, '', '/demo-accounts')
    render(<App />)

    expect(await screen.findByText(/Seeded Role Evaluation Personas/i)).toBeInTheDocument()

    for (const acc of DEMO_EVALUATION_ACCOUNTS) {
      expect(screen.getByText(acc.name)).toBeInTheDocument()
      expect(screen.getByText(acc.email)).toBeInTheDocument()
      expect(screen.getByText(acc.badge)).toBeInTheDocument()
    }
  })

  it('clicking "Use in sign in" passes email to the login screen', async () => {
    window.history.replaceState({}, '', '/demo-accounts')
    render(<App />)

    expect(await screen.findByText(/Seeded Role Evaluation Personas/i)).toBeInTheDocument()

    const selectButtons = screen.getAllByRole('button', { name: /use in sign in/i })
    expect(selectButtons.length).toBe(6)

    // Select the first account (Nadia Admin - admin@nfpl.test)
    fireEvent.click(selectButtons[0])

    // Should navigate to /login and prefill the email
    expect(await screen.findByRole('heading', { name: /sign in to your workspace/i })).toBeInTheDocument()
    const emailInput = screen.getByLabelText(/email address/i) as HTMLInputElement
    expect(emailInput.value).toBe('admin@nfpl.test')
  })

  it('evaluator persona pills on login page update the email field directly', async () => {
    window.history.replaceState({}, '', '/login')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /sign in to your workspace/i })).toBeInTheDocument()

    // Click Maker persona pill
    const makerPill = screen.getByRole('button', { name: /^maker$/i })
    fireEvent.click(makerPill)

    const emailInput = screen.getByLabelText(/email address/i) as HTMLInputElement
    expect(emailInput.value).toBe('emp-00@nfpl.test')

    // Click Client persona pill
    const clientPill = screen.getByRole('button', { name: /^client$/i })
    fireEvent.click(clientPill)
    expect(emailInput.value).toBe('client-viewer-00@portal.test')
  })

  it('displays the shared evaluation password and allows one-click fill', async () => {
    window.history.replaceState({}, '', '/login')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /sign in to your workspace/i })).toBeInTheDocument()

    // Confirms demo password is shown
    expect(screen.getByText('123123123123')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /copy password/i })).toBeInTheDocument()

    // Click "Fill Password" button
    const fillButton = screen.getByRole('button', { name: /fill password/i })
    fireEvent.click(fillButton)

    // Password input should have the demo password filled
    const passwordInput = screen.getByLabelText(/^password/i) as HTMLInputElement
    expect(passwordInput.value).toBe('123123123123')
  })

  it('displays the shared evaluation password banner on the demo accounts guide', async () => {
    window.history.replaceState({}, '', '/demo-accounts')
    render(<App />)

    expect(await screen.findByText(/Shared Evaluation Demo Password/i)).toBeInTheDocument()
    expect(screen.getByText('123123123123')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /copy demo password/i })).toBeInTheDocument()
  })
})
