# Mercury Coding Standards

## General

- Match nearby code and keep changes focused.
- Use clear names and small, testable functions.
- Avoid broad formatting or unrelated refactors.
- Add documentation when data definitions, API contracts, or analytical methods change.

## Python and Data

- Use `snake_case`, type hints, deterministic transformations, and explicit schemas.
- Prefer pandas/vectorized operations for tabular transformations when readable.
- Use parameterized SQL and explicit transaction handling.
- Keep money calculations precise and document units.

## FastAPI

- Keep Pydantic schemas explicit and validate all external input.
- Keep route handlers thin and return documented status codes and response shapes.
- Do not expose raw database exceptions or sensitive fields.

## React/TypeScript

- Use TypeScript, feature-local API functions, and accessible loading/error/empty states.
- Keep server data fetching separate from presentation components.
- Reuse the project design system once one exists.