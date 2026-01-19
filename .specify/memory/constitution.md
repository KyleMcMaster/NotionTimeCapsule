<!--
  SYNC IMPACT REPORT
  ==================
  Version change: 0.0.0 → 1.0.0 (initial ratification)
  
  Added principles:
  - I. Data Integrity First
  - II. Idempotent Operations
  - III. CLI-Driven Interface
  - IV. Test Coverage
  - V. Simplicity & Reliability
  
  Added sections:
  - Core Principles (5 principles)
  - Technical Constraints
  - Development Workflow
  - Governance
  
  Templates status:
  - plan-template.md: ✅ Compatible (Constitution Check section present)
  - spec-template.md: ✅ Compatible (Requirements section aligns)
  - tasks-template.md: ✅ Compatible (Phase structure aligns)
  
  Deferred items: None
-->

# NotionTimeCapsule Constitution

## Core Principles

### I. Data Integrity First

All backup operations MUST preserve the complete fidelity of Notion content:

- Markdown output MUST retain original structure, formatting, and metadata
- File attachments and embedded content MUST be downloaded and linked correctly
- Database properties MUST be preserved in a queryable format (frontmatter or structured files)
- Backup MUST be idempotent: re-running produces identical output for unchanged content
- Incremental backups MUST detect changes accurately to avoid data loss or duplication

**Rationale**: Users trust this tool with their knowledge base. Data corruption or loss is unacceptable.

### II. Idempotent Operations

Every operation MUST be safely repeatable without side effects:

- Running the same backup twice MUST produce identical results
- Interrupted operations MUST be resumable without corruption
- Failed operations MUST NOT leave partial or inconsistent state
- All file operations MUST use atomic writes (write-to-temp, then rename)

**Rationale**: Scheduled/automated backups may run unattended; predictable behavior is essential.

### III. CLI-Driven Interface

The application MUST expose all functionality through a CLI:

- All configuration MUST be specifiable via command-line arguments or environment variables
- Output MUST support both human-readable and JSON formats (`--json` flag)
- Progress reporting MUST go to stderr; data output MUST go to stdout
- Exit codes MUST follow Unix conventions (0 = success, non-zero = error with specific codes)

**Rationale**: Enables automation, scripting, and integration with scheduling tools (cron, launchd, systemd).

### IV. Test Coverage

Critical paths MUST have test coverage:

- Unit tests MUST cover Notion API response parsing and markdown generation
- Integration tests MUST verify end-to-end backup workflows with mock API responses
- Contract tests MUST validate behavior against expected Notion API shapes
- Tests MUST run in CI before merge to main branch

**Rationale**: Notion's API may change; tests provide early detection of breaking changes.

### V. Simplicity & Reliability

Prefer simple, maintainable solutions over complex optimizations:

- Start with synchronous, single-threaded operations; add parallelism only when proven necessary
- Dependencies MUST be minimal and well-maintained
- Configuration MUST have sensible defaults requiring minimal user setup
- YAGNI: Do not implement features speculatively

**Rationale**: A backup tool must be reliable above all else. Complexity introduces failure modes.

## Technical Constraints

- **Language**: Python 3.11+ (widely available, good library ecosystem for API integration)
- **Notion API**: Official Notion SDK or REST API with proper rate limiting and retry logic
- **Output Format**: Markdown files with YAML frontmatter for metadata
- **Storage**: Local filesystem as primary target; cloud storage integration as future enhancement
- **Authentication**: Notion integration token via environment variable (`NOTION_TOKEN`)
- **Scheduling**: External scheduler (cron/launchd); application handles single-run execution

## Development Workflow

1. **Specification First**: Features MUST be specified in `/specs/` before implementation
2. **Branch Strategy**: Feature branches named `[issue#]-feature-name`
3. **Testing Gate**: All tests MUST pass before merge
4. **Documentation**: README and CLI help MUST be updated with new features
5. **Versioning**: SemVer (MAJOR.MINOR.PATCH) for releases

## Governance

This constitution supersedes all other development practices for NotionTimeCapsule:

- All code changes MUST comply with the principles above
- Violations MUST be documented in the PR with explicit justification
- Constitution amendments require:
  1. Written proposal with rationale
  2. Version increment (following SemVer for governance changes)
  3. Update to this document with amendment date

**Version**: 1.0.0 | **Ratified**: 2026-01-18 | **Last Amended**: 2026-01-18
