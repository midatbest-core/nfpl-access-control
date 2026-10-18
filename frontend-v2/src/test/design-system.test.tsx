import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuditBadge } from '../components/design-system/AuditBadge'
import { ConfirmationDialog } from '../components/design-system/ConfirmationDialog'
import { EmptyState } from '../components/design-system/EmptyState'
import { FormField, TextInput } from '../components/design-system/FormElements'
import { SearchTable } from '../components/design-system/SearchTable'
import { DirectionBadge, ModeBadge, StatusBadge } from '../components/design-system/StatusBadge'

describe('Design System Components', () => {
  it('StatusBadge correctly renders stages, availability, modes, and directions', () => {
    const { rerender } = render(<StatusBadge status="prepared" />)
    expect(screen.getByText('Prepared')).toBeInTheDocument()

    rerender(<StatusBadge status="available" />)
    expect(screen.getByText('Available')).toBeInTheDocument()

    rerender(<ModeBadge mode="air" />)
    expect(screen.getByText('AIR')).toBeInTheDocument()

    rerender(<DirectionBadge direction="import" />)
    expect(screen.getByText('IMPORT')).toBeInTheDocument()
  })

  it('AuditBadge classifies actions and displays denial state', () => {
    const { rerender } = render(<AuditBadge action="prepare_job" denied={false} />)
    expect(screen.getByText('Workflow Transition')).toBeInTheDocument()
    expect(screen.getByText('Allowed')).toBeInTheDocument()

    rerender(<AuditBadge action="grant_role" denied={true} />)
    expect(screen.getByText('Role & Policy')).toBeInTheDocument()
    expect(screen.getByText('Denied')).toBeInTheDocument()
  })

  it('ConfirmationDialog supports confirmation and keyboard cancellation', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()

    const { rerender } = render(
      <ConfirmationDialog
        open={true}
        title="Revoke Role?"
        message="This action will take effect immediately."
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Revoke Role?')).toBeInTheDocument()

    const confirmBtn = screen.getByRole('button', { name: 'Confirm' })
    await userEvent.click(confirmBtn)
    expect(onConfirm).toHaveBeenCalledTimes(1)

    // Test ESC key
    await userEvent.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalledTimes(1)

    rerender(
      <ConfirmationDialog
        open={false}
        title="Revoke Role?"
        message="This action will take effect immediately."
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('FormField visibly marks required fields with asterisk and handles accessibility', () => {
    render(
      <FormField id="test-field" label="Client Identifier" required error="Required client identifier">
        <TextInput id="test-field" error={true} defaultValue="" />
      </FormField>,
    )

    expect(screen.getByText('*')).toHaveAttribute('title', 'Required field')
    expect(screen.getByRole('alert')).toHaveTextContent('Required client identifier')
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true')
  })

  it('EmptyState renders meaningful illustration, title, and action', () => {
    render(
      <EmptyState
        title="No shipments found"
        description="Try adjusting your filter parameters or search query."
        action={<button type="button">Reset Filters</button>}
      />,
    )

    expect(screen.getByText('No shipments found')).toBeInTheDocument()
    expect(screen.getByText(/adjusting your filter/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reset Filters' })).toBeInTheDocument()
  })

  it('SearchTable renders structured columns and pagination controls', () => {
    interface Item {
      id: string
      code: string
      name: string
    }

    const items: Item[] = [
      { id: '1', code: 'CL001', name: 'Acme Logistics' },
      { id: '2', code: 'CL002', name: 'Global Freight' },
    ]

    render(
      <SearchTable
        data={items}
        columns={[
          { key: 'code', header: 'Code', render: (item) => item.code },
          { key: 'name', header: 'Name', render: (item) => item.name },
        ]}
        keyExtractor={(item) => item.id}
        totalCount={2}
      />,
    )

    expect(screen.getByText('CL001')).toBeInTheDocument()
    expect(screen.getByText('Global Freight')).toBeInTheDocument()
    expect(screen.getByText(/showing 2 of 2 items/i)).toBeInTheDocument()
  })
})
