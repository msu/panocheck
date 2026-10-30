# GitHub Pages

- The MSU org has a free plan, so Pages needs a public repo. This is not tested.
- Environment rules can block deploys from tags. Use a manual workflow run on `main` if a tag deploy fails.
- The workflow publishes `src/web/site` as it is. There is no build step.
- All site URLs are relative, so the app works under `/panocheck/`.
