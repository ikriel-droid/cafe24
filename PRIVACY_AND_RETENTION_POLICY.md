# Privacy And Retention Policy

## Data Classes

ClaimMate handles:
- operator account data
- merchant account data
- customer support messages
- order and delivery identifiers
- AI invocation metadata
- audit and delivery logs

## Handling Principles

- collect only what is needed for claim handling
- mask secrets and sensitive fields in diagnostics
- restrict audit access by role
- separate merchants by tenant scope

## Retention

Current product policy should define:
- claim retention window
- audit log retention window
- reply delivery retention window
- AI invocation log retention window
- backup retention window

## Deletion And Review

- support soft delete where operationally required
- document when permanent deletion is allowed
- require legal review before promising customer-specific retention terms

## Current Status

The codebase includes retention controls and masking rules, but final legal review and contract language remain a business step outside the repository.
