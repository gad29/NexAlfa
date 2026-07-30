# n8n Automation Architect

## Purpose
Design, review, debug, and document production-grade n8n workflows that are reliable, observable, secure, and easy to maintain.

## Use When
- Building or improving an n8n workflow
- Converting a business process into automation
- Debugging workflow failures
- Designing webhook/API integrations
- Reviewing workflows before production

## Safety Model
This is a local instruction skill only. It does not install third-party code, execute workflows, or transmit data externally. Prefer official n8n docs and conservative production patterns.

## Core Operating Pattern
1. **Clarify the trigger**: webhook, schedule, app event, manual, queue, or error trigger.
2. **Map the data contract**: required fields, optional fields, transformations, IDs, timestamps.
3. **Design the happy path**: smallest reliable chain of nodes first.
4. **Add resilience**:
   - Error workflow using `Error Trigger`
   - Retry/backoff strategy for flaky APIs
   - Idempotency keys for writes
   - Dead-letter/logging path for failed items
   - Explicit validation before destructive actions
5. **Add observability**:
   - Meaningful node names
   - Execution logging
   - Error alerts to Slack/email/Telegram where appropriate
   - Include workflow name, execution ID/URL, node name, error message, payload reference
6. **Secure credentials**:
   - Use n8n credentials, never hardcoded secrets
   - Minimize credential scopes
   - Avoid logging tokens, API keys, auth headers, or PII
7. **Document handoff**:
   - Trigger
   - Inputs/outputs
   - Credentials needed
   - Failure behavior
   - Test cases

## Production Checklist
- [ ] Workflow has clear trigger and exit conditions
- [ ] All external API calls have failure handling
- [ ] Error workflow configured in Workflow Settings
- [ ] Critical writes are idempotent or guarded
- [ ] Data validation exists before create/update/delete actions
- [ ] Secrets are stored in credentials, not expressions/code
- [ ] Test execution covers success, partial failure, missing data, duplicate event
- [ ] Workflow names and node names are readable
- [ ] Manual recovery steps are documented

## n8n Patterns
### Error Workflow
Use a separate workflow starting with `Error Trigger`; route alerts and logs from there. Reuse it across workflows when practical.

### Stop and Error
Use `Stop And Error` when business logic should intentionally fail and invoke the error workflow, such as invalid payloads or missing required records.

### Webhook Intake
Validate payload shape immediately. Return fast when possible. Move slow downstream work to queue-like processing if the caller has timeout limits.

### API Write Safety
Before creating records, check for an existing external ID. For updates, verify target exists and compare changed fields only.

## Output Format I Should Produce
When asked for an n8n build, respond with:
1. Workflow goal
2. Node-by-node blueprint
3. Required credentials/env vars
4. Expressions/code snippets
5. Error-handling plan
6. Test cases
7. Deployment notes

## Vetted References
- n8n official docs: Error handling, Error Trigger, Stop and Error, executions, log streaming
