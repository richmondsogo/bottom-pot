const UNSAFE_ERROR_MESSAGE_RE =
  /\b(http\s*\d{3}|exception|traceback|typeerror|syntaxerror|referenceerror|failed to fetch|networkerror|ats|serper|postgres|sqlite|stack|upstream|simulation|simulated|provider_error)\b/i;

export function getSafeErrorDescription(
  message?: string,
  isRateLimited?: boolean,
  mode: 'user' | 'admin' = 'user'
): string {
  const defaultBody = isRateLimited
    ? 'Please wait a little before trying again.'
    : 'Something went wrong while searching. Try again in a moment.';

  if (mode === 'admin') {
    return message?.trim() || defaultBody;
  }

  const trimmed = message?.trim();
  if (!trimmed || trimmed.length > 200 || trimmed.includes('\n')) {
    return defaultBody;
  }
  if (UNSAFE_ERROR_MESSAGE_RE.test(trimmed)) {
    return defaultBody;
  }
  return trimmed;
}
