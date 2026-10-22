// Rows added in the editor carry a client-only marker until the server has
// saved them. Only marked rows take their key from the name, so a saved key
// can never be re-derived by accident. `tidy` strips the marker before saving.
export function markNew<T extends object>(row: T): T {
  return { ...row, _new: true }
}

export const isNew = (row: object) => (row as { _new?: boolean })._new === true

export function unmark<T extends object>(row: T): T {
  const { _new: _drop, ...rest } = row as T & { _new?: boolean }
  void _drop
  return rest as T
}
