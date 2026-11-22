import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { DataTable, type DataTableColumn, type DataTableLabels } from './DataTable';

afterEach(cleanup);

interface Device {
  id: string;
  name: string;
  ports: number;
}

const devices: Device[] = [
  { id: 'a', name: 'core', ports: 48 },
  { id: 'b', name: 'access', ports: 24 },
  { id: 'c', name: 'edge', ports: 8 },
];

const columns: DataTableColumn<Device>[] = [
  { key: 'name', header: 'Name', cell: (d) => d.name, sortValue: (d) => d.name },
  {
    key: 'ports',
    header: 'Ports',
    cell: (d) => d.ports,
    sortValue: (d) => d.ports,
    align: 'right',
  },
];

const labels: DataTableLabels<Device> = {
  selectAll: 'Select all',
  selectRow: (d) => `Select ${d.name}`,
  actions: 'Actions',
  pagination: 'Pages',
  previousPage: 'Previous page',
  nextPage: 'Next page',
  pageStatus: (page, count, total) => `Page ${page} of ${count} (${total} rows)`,
};

function names(): string[] {
  return screen
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[0]?.textContent ?? '');
}

const table = (extra: Partial<React.ComponentProps<typeof DataTable<Device>>> = {}) => (
  <DataTable
    rows={devices}
    columns={columns}
    getRowKey={(d) => d.id}
    caption="Devices"
    empty={<p>none</p>}
    labels={labels}
    {...extra}
  />
);

function SelectableTable() {
  const [selectedKeys, setSelected] = useState<ReadonlySet<string>>(new Set());
  return table({ selection: { selectedKeys, onChange: setSelected } });
}

describe('DataTable', () => {
  it('renders a named semantic table with column headers and a row per item', () => {
    render(table());
    expect(screen.getByRole('table', { name: 'Devices' })).toBeTruthy();
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Name',
      'Ports',
    ]);
    expect(names()).toEqual(['core', 'access', 'edge']);
  });

  it('shows the empty node instead of a table when there are no rows', () => {
    render(table({ rows: [] }));
    expect(screen.getByText('none')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('cycles a column ascending, descending, then off, with aria-sort tracking it', () => {
    render(table());
    const header = screen.getByRole('columnheader', { name: /Name/ });
    const sortButton = within(header).getByRole('button');
    expect(header.getAttribute('aria-sort')).toBe('none');

    fireEvent.click(sortButton);
    expect(header.getAttribute('aria-sort')).toBe('ascending');
    expect(names()).toEqual(['access', 'core', 'edge']);

    fireEvent.click(sortButton);
    expect(header.getAttribute('aria-sort')).toBe('descending');
    expect(names()).toEqual(['edge', 'core', 'access']);

    fireEvent.click(sortButton);
    expect(header.getAttribute('aria-sort')).toBe('none');
    expect(names()).toEqual(['core', 'access', 'edge']);
  });

  it('sorts numbers numerically and applies a default sort', () => {
    render(table({ defaultSort: { key: 'ports', direction: 'asc' } }));
    expect(names()).toEqual(['edge', 'access', 'core']);
  });

  it('exposes a sortable header as a focusable native button, so Enter and Space sort it', () => {
    render(table());
    const sortButton = within(screen.getByRole('columnheader', { name: /Ports/ })).getByRole(
      'button',
    );
    sortButton.focus();
    expect(document.activeElement).toBe(sortButton);
    expect(sortButton.tagName).toBe('BUTTON');
  });

  it('leaves a column without a sortValue as plain text with no aria-sort', () => {
    render(table({ columns: [{ key: 'name', header: 'Name', cell: (d) => d.name }] }));
    const header = screen.getByRole('columnheader', { name: 'Name' });
    expect(within(header).queryByRole('button')).toBeNull();
    expect(header.getAttribute('aria-sort')).toBeNull();
  });

  it('paginates, hides the pager for one page, and clamps after a sort', () => {
    const many = Array.from({ length: 7 }, (_, i) => ({ id: `${i}`, name: `d${i}`, ports: i }));
    render(table({ rows: many, pageSize: 3 }));
    expect(names()).toEqual(['d0', 'd1', 'd2']);
    expect(screen.getByText('Page 1 of 3 (7 rows)')).toBeTruthy();
    expect(
      (screen.getByRole('button', { name: 'Previous page' }) as HTMLButtonElement).disabled,
    ).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(names()).toEqual(['d6']);
    expect((screen.getByRole('button', { name: 'Next page' }) as HTMLButtonElement).disabled).toBe(
      true,
    );

    fireEvent.click(within(screen.getByRole('columnheader', { name: /Name/ })).getByRole('button'));
    expect(screen.getByText('Page 1 of 3 (7 rows)')).toBeTruthy();
  });

  it('shows no pager when everything fits on one page', () => {
    render(table());
    expect(screen.queryByRole('navigation', { name: 'Pages' })).toBeNull();
  });

  it('selects rows and selects all on the page, with an indeterminate header', () => {
    render(<SelectableTable />);
    const all = screen.getByRole('checkbox', { name: 'Select all' }) as HTMLInputElement;

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select core' }));
    expect(all.indeterminate).toBe(true);
    expect(all.checked).toBe(false);

    fireEvent.click(all);
    expect(all.checked).toBe(true);
    expect(all.indeterminate).toBe(false);
    expect(screen.getAllByRole('checkbox', { checked: true })).toHaveLength(4);

    fireEvent.click(all);
    expect(screen.queryAllByRole('checkbox', { checked: true })).toHaveLength(0);
  });

  it('renders a row-actions cell with a screen-reader header', () => {
    render(table({ rowActions: (d) => <button type="button">{`Edit ${d.name}`}</button> }));
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Edit core' })).toBeTruthy();
  });

  it('contains horizontal overflow inside the table frame at 390px', () => {
    render(table({ 'data-testid': 'dt' }));
    const frame = screen.getByTestId('dt');
    expect(frame.className).toContain('panel');
    expect(frame.className).toContain('min-w-0');
    expect(frame.className).toContain('overflow-hidden');
    const scroller = screen.getByRole('table').parentElement;
    expect(scroller?.className).toContain('overflow-x-auto');
    expect(scroller?.getAttribute('data-phone-width-exempt')).toBe('table-scroll');
  });

  it('holds a 44px row and a 40px header', () => {
    render(table());
    const [header, firstRow] = screen.getAllByRole('row');
    expect(header?.className).toContain('h-10');
    expect(firstRow?.className).toContain('h-11');
  });
});
