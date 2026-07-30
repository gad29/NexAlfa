# Airtable Architect

## Purpose
Design Airtable bases, automations, scripts, interfaces, and API integrations that are scalable, clean, and safe.

## Use When
- Building or improving an Airtable base
- Creating automations or scripts
- Integrating Airtable with n8n, Make, APIs, or apps
- Fixing messy tables/fields
- Designing CRM, project tracker, content ops, inventory, lead pipelines, or internal tools

## Safety Model
This skill is local guidance only. It does not access Airtable or run scripts unless credentials and explicit instructions are provided. Secrets must stay in Airtable secrets/credentials or local env vars, never hardcoded.

## Base Design Principles
1. **Model entities, not views**: tables should represent real objects like Contacts, Companies, Projects, Tasks, Orders.
2. **Use linked records for relationships** instead of duplicating text.
3. **Normalize where it matters**: avoid repeated fields like `Client 1`, `Client 2`.
4. **Use stable IDs** for integrations: external IDs, slugs, unique keys.
5. **Separate raw intake from clean operational tables** when importing messy data.
6. **Prefer single-selects for controlled states**; avoid free-text statuses.
7. **Use formula/lookup/rollup fields for derived data**, not manually maintained copies.
8. **Create filtered views for automation triggers** to control exactly what runs.

## Automation/Scripting Checklist
- [ ] Trigger condition is specific and avoids loops
- [ ] Script receives explicit input variables
- [ ] Secrets use Airtable secret variables or external credential storage
- [ ] Script handles missing records/fields gracefully
- [ ] Mutations are batched where possible
- [ ] Rate/limit constraints are respected
- [ ] Output variables are small and intentional
- [ ] Test automation before turning ON
- [ ] Run history/logs are checked after deployment

## Airtable Script Limits To Remember
- Automation script runtime is limited
- Airtable scripting API calls can timeout
- Fetch requests have timeout limits
- Memory is limited
- Fetch/select/mutation counts are limited
- Batch record mutations where possible, typically up to 50 records per mutation call

## Integration Pattern
For Airtable + n8n/Make/API:
1. Define source of truth
2. Choose unique key for upsert
3. Read existing record by unique key
4. Create/update only changed fields
5. Write sync status and last synced timestamp
6. Log errors with enough context but no secrets

## Output Format I Should Produce
1. Data model/table design
2. Field list with types
3. Views needed
4. Automations/scripts
5. Integration/API plan
6. Validation and dedupe rules
7. Testing checklist

## Vetted References
- Airtable official docs: Run a script action, scripting API, automations, API docs
