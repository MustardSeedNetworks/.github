/**
 * DataTable: the one table. A semantic <table> in a hairline frame, with a
 * sticky-free header, 44px rows, sortable columns, optional selection and row
 * actions, and a pager.
 *
 * Based on niac's DataTable (typed columns that own their cells, a sort that
 * cycles ascending, descending, off, and select-all) with its virtual
 * scrolling, loading branch and row-click removed, and pagination, `aria-sort`
 * and the contained scroll added. seed's table, stem's list and niac's CSS-grid
 * device list all give way to this.
 *
 * At 390px the table scrolls sideways inside its own frame, never the page,
 * and says so with `data-phone-width-exempt`, which the fleet's phone-width
 * gate needs to tell a deliberate scroller from content leaving the viewport.
 * The sort buttons, checkboxes and row actions are focusable, and current
 * browsers make a scroller with none focusable on their own, so a keyboard user
 * can always pan it. The table is named by its `caption`.
 *
 * Pagination, sorting and selection are client-side over `rows`. A list that
 * is paged by the server is not this component; do not fake it by passing one
 * page of rows and a `pageSize` that hides the pager.
 */
import { ChevronDown, ChevronLeft, ChevronRight, ChevronsUpDown, ChevronUp } from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import { cx } from './cx';

export interface DataTableColumn<T> {
  /** Stable id, also the sort key. */
  key: string;
  /** Already translated. */
  header: string;
  cell: (row: T) => ReactNode;
  /** Makes the column sortable by this value. */
  sortValue?: (row: T) => string | number;
  align?: 'left' | 'right';
}

export interface DataTableSelection {
  selectedKeys: ReadonlySet<string>;
  onChange: (keys: ReadonlySet<string>) => void;
}

export interface DataTableLabels<T> {
  /** Select-all checkbox, which covers the rows on the current page. */
  selectAll: string;
  selectRow: (row: T) => string;
  /** Screen-reader header of the row-actions column. */
  actions: string;
  /** Accessible name of the pager landmark. */
  pagination: string;
  previousPage: string;
  nextPage: string;
  /** e.g. "Page 2 of 5 (113 rows)". */
  pageStatus: (page: number, pageCount: number, total: number) => string;
}

export interface DataTableProps<T> {
  rows: readonly T[];
  columns: readonly DataTableColumn<T>[];
  getRowKey: (row: T) => string;
  /** Names the table and its scroll region. Already translated. */
  caption: string;
  /** Shown instead of the table when there are no rows: an EmptyState. */
  empty: ReactNode;
  labels: DataTableLabels<T>;
  defaultSort?: { key: string; direction: 'asc' | 'desc' };
  /** Rows per page. The pager appears only when there is more than one page. */
  pageSize?: number;
  selection?: DataTableSelection;
  /** The last column: one to three icon buttons or a menu. */
  rowActions?: (row: T) => ReactNode;
  'data-testid'?: string;
}

type SortState = { key: string; direction: 'asc' | 'desc' } | null;

const DEFAULT_PAGE_SIZE = 25;

function compare(a: string | number, b: string | number): number {
  return typeof a === 'number' && typeof b === 'number'
    ? a - b
    : String(a).localeCompare(String(b));
}

function SortIcon({ direction }: { direction: 'asc' | 'desc' | null }) {
  const Icon = { asc: ChevronUp, desc: ChevronDown, none: ChevronsUpDown }[direction ?? 'none'];
  return (
    <Icon
      className={cx('h-3.5 w-3.5 shrink-0', direction ? 'text-text-primary' : 'text-text-muted')}
      aria-hidden="true"
    />
  );
}

function ariaSort(direction: 'asc' | 'desc' | null): 'ascending' | 'descending' | 'none' {
  if (direction === null) {
    return 'none';
  }
  return direction === 'asc' ? 'ascending' : 'descending';
}

const cellPad = 'px-4 py-2';
const checkboxClass = 'h-4 w-4 accent-brand-primary';

export function DataTable<T>({
  rows,
  columns,
  getRowKey,
  caption,
  empty,
  labels,
  defaultSort,
  pageSize = DEFAULT_PAGE_SIZE,
  selection,
  rowActions,
  'data-testid': testId,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState>(defaultSort ?? null);
  const [requestedPage, setRequestedPage] = useState(1);
  const selectAllRef = useRef<HTMLInputElement>(null);

  const sortColumn = sort ? columns.find((column) => column.key === sort.key) : undefined;
  const sortValue = sortColumn?.sortValue;
  const sortedRows =
    sort && sortValue
      ? [...rows].sort(
          (a, b) => (sort.direction === 'asc' ? 1 : -1) * compare(sortValue(a), sortValue(b)),
        )
      : rows;

  const pageCount = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const page = Math.min(requestedPage, pageCount);
  const pageRows = sortedRows.slice((page - 1) * pageSize, page * pageSize);

  const pageKeys = pageRows.map(getRowKey);
  const selectedOnPage = selection ? pageKeys.filter((key) => selection.selectedKeys.has(key)) : [];
  const allSelected = pageKeys.length > 0 && selectedOnPage.length === pageKeys.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedOnPage.length > 0 && !allSelected;
    }
  }, [selectedOnPage.length, allSelected]);

  if (rows.length === 0) {
    return <div data-testid={testId}>{empty}</div>;
  }

  const toggleSort = (key: string) => {
    setRequestedPage(1);
    setSort((previous) => {
      if (previous?.key !== key) {
        return { key, direction: 'asc' };
      }
      return previous.direction === 'asc' ? { key, direction: 'desc' } : null;
    });
  };

  const toggleAll = () => {
    if (!selection) {
      return;
    }
    const next = new Set(selection.selectedKeys);
    for (const key of pageKeys) {
      if (allSelected) {
        next.delete(key);
      } else {
        next.add(key);
      }
    }
    selection.onChange(next);
  };

  const toggleRow = (key: string) => {
    if (!selection) {
      return;
    }
    const next = new Set(selection.selectedKeys);
    if (!next.delete(key)) {
      next.add(key);
    }
    selection.onChange(next);
  };

  return (
    <div className="panel min-w-0 overflow-hidden" data-testid={testId}>
      <div className="overflow-x-auto" data-phone-width-exempt="table-scroll">
        <table className="w-full min-w-max text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-sunken text-xs uppercase tracking-wide text-text-muted">
            <tr className="h-10">
              {selection ? (
                <th scope="col" className={cx(cellPad, 'w-10 text-left')}>
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label={labels.selectAll}
                    className={checkboxClass}
                  />
                </th>
              ) : null}
              {columns.map((column) => {
                const direction = sort?.key === column.key ? sort.direction : null;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={column.sortValue ? ariaSort(direction) : undefined}
                    className={cx(
                      cellPad,
                      'font-semibold',
                      column.align === 'right' ? 'text-right' : 'text-left',
                    )}
                  >
                    {column.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.key)}
                        className={cx(
                          'inline-flex items-center gap-1 uppercase tracking-wide hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary',
                          direction && 'text-text-primary',
                        )}
                      >
                        {column.header}
                        <SortIcon direction={direction} />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
              {rowActions ? (
                <th scope="col" className={cellPad}>
                  <span className="sr-only">{labels.actions}</span>
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline text-text-secondary">
            {pageRows.map((row) => {
              const key = getRowKey(row);
              const selected = selection?.selectedKeys.has(key) ?? false;
              return (
                <tr
                  key={key}
                  aria-selected={selection ? selected : undefined}
                  className={cx('h-11 hover:bg-surface-hover', selected && 'bg-surface-hover')}
                >
                  {selection ? (
                    <td className={cellPad}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleRow(key)}
                        aria-label={labels.selectRow(row)}
                        className={checkboxClass}
                      />
                    </td>
                  ) : null}
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cx(cellPad, column.align === 'right' && 'text-right')}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                  {rowActions ? (
                    <td className={cx(cellPad, 'text-right')}>
                      <div className="inline-flex items-center gap-1">{rowActions(row)}</div>
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pageCount > 1 ? (
        <nav
          aria-label={labels.pagination}
          className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline px-4 py-2 text-xs text-text-muted"
        >
          <span aria-live="polite">{labels.pageStatus(page, pageCount, sortedRows.length)}</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setRequestedPage(page - 1)}
              disabled={page === 1}
              aria-label={labels.previousPage}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-primary hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:cursor-not-allowed disabled:text-text-disabled disabled:hover:bg-transparent"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => setRequestedPage(page + 1)}
              disabled={page === pageCount}
              aria-label={labels.nextPage}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-primary hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:cursor-not-allowed disabled:text-text-disabled disabled:hover:bg-transparent"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
