---
name: deploy
description: Deploy the application to production via make deploy
disable-model-invocation: false
---

Deploy the application to production:

1. Run `make deploy` which pushes to main and deploys via SSH to the Hetzner VPS
2. Monitor the output for build or deployment errors
3. Report the result — success or failure with details
