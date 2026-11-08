# Operator guide

Use a local single-user instance. The sequence prepares synthetic proposals and never dispatches a vehicle. Public provider availability and municipal snapshots vary; an unsuccessful bypass is a valid outcome.

## Start

Follow [Run locally](../README.md#run-locally), open `http://localhost:3000`, and select the light theme. Do not replace an existing private `.env` with an example file. For the real agent, configure Gemini or Groq in the backend; the manual road engine works without a model key.

1. **Load original routes.** This creates road scenario A without a proposal.
2. **Load city data.** Check individual source results and downloaded/observed timestamps. A failed feed stays unavailable.
3. **Prepare the fleet.** Ask:

   > Recalculate the full fictional fleet using prepare_dispatch_proposal, inspect_dispatch_decision and compare_dispatch_scenarios, then show B versus C on the map. Do not approve or dispatch.

4. **Investigate without mutation.** Ask:

   > Inspect all three fleet routes in B using investigate_fleet_disruptions without replanning. Then focus V-02 in scenario B, highlight its nearby incident points and sensor readings. Separate observed measurements from proximity. Do not prepare, approve or dispatch.

   Confirm the plan ID/generation are unchanged, V-02/B is selected and no approval card is inherited from the previous request. The actual trace should include the fleet-review node events and invoked tools.

5. **Inspect a notice.** Open Incident Intelligence, choose a published notice, inspect its nearby observations and optionally open/close a camera still. This geographic join is read-only.
6. **Request hypothetical avoidance.** Ask:

   > For the WHOLE FLEET, use prepare_precautionary_avoidance with vehicle_id ALL to verify preventative street bypasses around nearby municipal notice buffers. Ignore previous map selections. Report successes and failures for all three vans and show B versus C. Treat buffers as hypothetical, never verified closures. Do not approve or dispatch.

   Compare B/C and read every vehicle outcome. In the recorded run only V-01 had a verified partial bypass; V-02/V-03 remained unchanged. No alternative is guaranteed for a later snapshot. Provider checks can take time because requests are paced and bounded.
7. **Review the trace.** Open AI Agent and inspect executed tools, outputs and the pending-proposal gate. Only the operator may choose **Approve simulated plan**. Approval records a local synthetic decision, not a real dispatch.

## No-key path

With `AGENT_PROVIDER=demo`, request a read-only fleet count or source review. The UI must identify the deterministic demo engine. Use **Advanced actions → Recalculate with road engine (no LLM)** for road proposals, and **Verify preventative bypasses (routing engine)** for a manual hypothetical check. Both require external routing availability, but no LLM credentials.

## Results and evidence

The [verification record](verification.md) gives observed metrics, tests, security audit and remaining limits. All five screenshots in [`media/screenshots/`](../media/screenshots/) come from the running application in the light theme. Synthetic metrics must remain labelled when sharing the demo.

```bash
./scripts/smoke.sh
# Stop this project's services when finished:
docker compose down
```
