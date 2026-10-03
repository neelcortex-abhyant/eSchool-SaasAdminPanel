# Fixture sanitization rules

## Remove or replace

- Passwords, OTP codes, reset tokens
- Sanctum plain tokens (keep shape `{id}|{redacted}` if needed for docs; never commit real plains)
- Payment secrets, webhook signing secrets, gateway keys
- FCM / web push tokens
- Real emails, phones, street addresses when policy requires
- APP_KEY material, Reverb secrets

## Preserve exactly

- Numeric IDs and foreign keys
- Scalar types (int vs string `"1"`, bool vs `0/1`, null vs missing)
- Nested relationship graphs and list order
- Pagination shapes and value types
- Filenames, content types, PDF/HTML markers
- Localized `message` strings and numeric `code` values
- Role-specific login resource shape (student / parent+children / teacher / school-admin / driver)

## Process

1. Capture raw response from Laravel into a private local file (gitignored).
2. Run sanitizer checklist; produce `fixtures/golden/...`.
3. Record `source_capture` metadata: environment, school-code (sanitized), timestamp, Laravel version fingerprint.
4. Never commit `datasets/*.sql` with PII.
