# DAG / WBS

1. Confirm GitHub auth and remote target.
2. Create or attach the `origin` remote.
3. Add session docs scaffold.
4. Commit the initial repo state.
5. Push to GitHub.
6. Re-run local validation if any packaging or docs changes touched runtime files.

Critical path:
- Remote creation blocks publishing.
- Publishing blocks any later PR/issue workflow.
