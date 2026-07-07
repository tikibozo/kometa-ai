# Changelog

## [0.4.0](https://github.com/tikibozo/kometa-ai/compare/v0.3.0...v0.4.0) (2026-07-07)


### Features

* pace backfill with candidate prefilter, per-run budget, prompt caching ([#17](https://github.com/tikibozo/kometa-ai/issues/17)) ([d18f293](https://github.com/tikibozo/kometa-ai/commit/d18f2933e5940b277769b78b6a9d190c3c1f5e8c))

## [0.3.0](https://github.com/tikibozo/kometa-ai/compare/v0.2.6...v0.3.0) (2026-07-07)


### Features

* re-evaluate a collection when its prompt changes ([#14](https://github.com/tikibozo/kometa-ai/issues/14)) ([1d4bbf9](https://github.com/tikibozo/kometa-ai/commit/1d4bbf94f6912a3e0fea25e57a3c41a90fc8b314))


### Bug Fixes

* prevent concurrent runs from clobbering Radarr tags ([#15](https://github.com/tikibozo/kometa-ai/issues/15)) ([4aa27c7](https://github.com/tikibozo/kometa-ai/commit/4aa27c73cb7ce617e11d4e5a025fd4fa3b6d64d9))

## [0.2.6](https://github.com/tikibozo/kometa-ai/compare/v0.2.5...v0.2.6) (2026-07-07)


### Bug Fixes

* stop the run gracefully when Claude hits a usage limit ([#12](https://github.com/tikibozo/kometa-ai/issues/12)) ([2513873](https://github.com/tikibozo/kometa-ai/commit/2513873d2ee1eadb196f4acf280a15234826c63a))

## [0.2.5](https://github.com/tikibozo/kometa-ai/compare/v0.2.4...v0.2.5) (2026-07-06)


### Documentation

* document CLAUDE_CODE_OAUTH_TOKEN auth for the cli backend ([5546d25](https://github.com/tikibozo/kometa-ai/commit/5546d25f322dccf9d73aa048ecf93b79af5aa0a9))

## [0.2.4](https://github.com/tikibozo/kometa-ai/compare/v0.2.3...v0.2.4) (2026-07-06)


### Bug Fixes

* strip YAML quoting from parsed collection names ([#9](https://github.com/tikibozo/kometa-ai/issues/9)) ([c6dd38b](https://github.com/tikibozo/kometa-ai/commit/c6dd38b969a32556e5ac95413b1f7ee4401ccfc8))

## [0.2.3](https://github.com/tikibozo/kometa-ai/compare/v0.2.2...v0.2.3) (2026-07-06)


### Bug Fixes

* tolerate a read-only kometa-config mount in the entrypoint ([#7](https://github.com/tikibozo/kometa-ai/issues/7)) ([58a2ade](https://github.com/tikibozo/kometa-ai/commit/58a2ade4684f9b6727b8e0a7caf087c55eb45f72))

## [0.2.2](https://github.com/tikibozo/kometa-ai/compare/v0.2.1...v0.2.2) (2026-07-06)


### Bug Fixes

* entrypoint installs the Claude CLI on demand for CLAUDE_BACKEND=cli ([#5](https://github.com/tikibozo/kometa-ai/issues/5)) ([d58ac52](https://github.com/tikibozo/kometa-ai/commit/d58ac523ca1dd0cddcb064695a36337031b2fe34))

## [0.2.1](https://github.com/tikibozo/kometa-ai/compare/v0.2.0...v0.2.1) (2026-07-06)


### Bug Fixes

* **deps:** move base image off EOL bullseye to python:3.12-slim ([694d02b](https://github.com/tikibozo/kometa-ai/commit/694d02b45c4d00e0ad3f89a5f327f299dfc94037))

## [0.2.0](https://github.com/tikibozo/kometa-ai/compare/v0.1.0...v0.2.0) (2026-07-06)


### Features

* fix decision oscillation, add subscription backend and metadata enrichment ([#1](https://github.com/tikibozo/kometa-ai/issues/1)) ([971ffc7](https://github.com/tikibozo/kometa-ai/commit/971ffc7d2683dd84870d44e6a25b5d92d6ec6d92))
