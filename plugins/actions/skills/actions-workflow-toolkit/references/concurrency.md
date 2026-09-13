# Workflow and job concurrency

Use this procedure when a deployment may be superseded, work is held by a
concurrency group, or a refactor changes scheduling policy. A scalar
`concurrency` value is a valid group shorthand; a scalar `environment` names
the deployment environment. Neither requires an object just to be valid.

1. Record the workflow/job scope, resolved group expression, and competing
   work. Keep environment approvals separate from concurrency and runner
   allocation; an unassigned runner alone does not identify the holding rule.
2. Evaluate running and pending work separately:

   | State | Default behavior and relevant control |
   | --- | --- |
   | Running | Omitting `cancel-in-progress`, or setting it to false, does not cancel the running item when newer work arrives. |
   | Pending | The default single-pending policy replaces older pending work with newer pending work, even when running cancellation is disabled. |

3. Do not describe the default policy as a lossless FIFO queue: not every
   pending deployment survives, and push/dispatch order does not guarantee
   execution order. State which work can finish and which pending work can
   be superseded.
4. Separate valid syntax from the intended release policy. Determine whether
   only the latest revision should deploy or every revision must be retained.
   Preserve the environment's approval boundary and account for the effect
   of interrupting a running deployment before proposing cancellation changes.
5. Before recommending an alternative pending-queue policy, verify its current
   syntax, compatibility with cancellation settings, and ordering basis in the
   [official concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
   Do not assume an omitted option selects that alternative or copy a queue
   limit from memory.
