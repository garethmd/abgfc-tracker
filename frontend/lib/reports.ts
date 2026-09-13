/** Same-origin download link for the one-page matchday sheet (coaches only). */
export function matchdaySheetUrl(teamSeasonId: number, fixtureId?: number): string {
  const base = `/api/v1/team-seasons/${teamSeasonId}/reports/matchday.pdf`;
  return fixtureId ? `${base}?fixture_id=${fixtureId}` : base;
}
