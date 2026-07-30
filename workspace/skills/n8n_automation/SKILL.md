# n8n_automation

## Description
System skill for building and managing n8n workflows using native n8n-mcp tools.

## When to Use
Use this whenever the user asks to build an automation, connect APIs, trigger webhooks, or explicitly mentions n8n.

## Steps
1. Always use `search_templates` or `search_nodes` to find community workflows or nodes.
2. Use `get_node` to understand the parameters required for any node before creating it.
3. Use `n8n_create_workflow` to assemble the workflow.
4. IMPORTANT: Always configure `branch: "true"|"false"` on connections exiting an `If Node` or `Switch` node.
5. Provide the user with the deployed workflow link or testing URL.

## Notes
n8n runs directly within the NexAlfa system context. Workflows deployed here will run in the background. You can use `n8n_test_workflow` to execute them immediately.
