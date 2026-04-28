# Known Issues

## Current

- Echo cleanup is only guaranteed when `AGENT_IMESSAGE_ECHO_DELETE_CMD` is configured.
- Expiration is record-based and requires an explicit sweep call.

## Follow-up candidates

- Add a first-class native deletion adapter if a stable Messages deletion surface appears.
- Add a background sweeper if the queue needs autonomous expiry processing.

