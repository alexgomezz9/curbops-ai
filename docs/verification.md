# Verification

## Recorded local checks — 5 November 2026

- Backend: 103 tests passed, including the explicit fleet-review graph tests.
- Frontend: TypeScript type checking and the production Next.js build passed.
- The read-only API smoke check passed against an isolated local API instance.
- Compose configuration parsed successfully; container images were not rebuilt as part of this import.

These checks apply to the imported source version. The latest UI has not received a complete end-to-end browser review. CI results are recorded separately by GitHub Actions.

## Local checks

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd frontend
npm ci
cd ..
./scripts/verify.sh
```

The backend suite mocks external providers. Frontend `lint` runs TypeScript type checking; `build` runs the production Next.js compiler. Neither proves that external feeds, model credentials or routing services work.

With the local backend running, `./scripts/smoke.sh` performs read-only health and mission/scenario contract checks. It does not recalculate, approve or dispatch a plan. A successful smoke check does not certify the complete operator workflow.

## Browser checks

Verify the current release on desktop: navigation, map layers, comparison pairs, free-form chat, actual tool/SSE events, source errors and human approval boundaries. Check map focus after a cache refresh and inspect read-only inquiries with a previous proposal present. Keep the fictional fleet, hypothetical incidents and provider base times clearly labelled.

Screenshots and a demo recording are deferred until the next UI version. No visual proof from an older build is presented as evidence for a newer release.

## Dependency audit

On 5 November 2026, `npm audit` reported three affected packages in the committed dependency tree: MapLibre GL (critical), PostCSS (high) and Next.js (moderate, through PostCSS). These are unresolved package advisories, not demonstrated exploitation of this application. A successful build does not clear them.

Remediation requires dependency changes and compatibility testing; it is separate from importing the current project. Run `npm audit` against the installed lockfile to inspect current advisory details. This repository is a local, single-user prototype, not an approved public deployment.
