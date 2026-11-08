const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u;

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function isValidEmail(email: string): boolean {
  const normalized = normalizeEmail(email);
  return normalized.length <= 254 && EMAIL_PATTERN.test(normalized);
}

export function passwordValidationError(password: string): string | null {
  const length = [...password].length;
  if (length < 8) return "La contraseña debe tener al menos 8 caracteres.";
  if (length > 128) return "La contraseña no puede superar los 128 caracteres.";
  if (new TextEncoder().encode(password).length > 72) {
    return "La contraseña es demasiado larga; reduce su longitud.";
  }
  if (!/\p{L}/u.test(password)) {
    return "Incluye al menos una letra.";
  }
  if (!/[\p{N}\p{P}\p{S}]/u.test(password)) {
    return "Incluye al menos un número o símbolo.";
  }
  return null;
}
