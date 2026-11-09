export class RangeResponseError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "RangeResponseError";
    this.status = status;
  }
}

type RangeResponse = Pick<Response, "status" | "headers" | "arrayBuffer">;
type RangeFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

function abortError(signal: AbortSignal): Error {
  return signal.reason instanceof Error
    ? signal.reason
    : new DOMException("La operación fue cancelada", "AbortError");
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError(signal));
      return;
    }
    const timer = globalThis.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      globalThis.clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      reject(abortError(signal));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export async function readRangeResponse(
  response: RangeResponse,
  start: number,
  end: number,
  signal?: AbortSignal,
): Promise<Uint8Array> {
  if (signal?.aborted) throw abortError(signal);
  if (response.status !== 206) {
    throw new RangeResponseError(
      response.status === 200
        ? "El servidor ignoró la solicitud HTTP Range; se rechazó la descarga completa."
        : `La solicitud Range respondió HTTP ${response.status}.`,
      response.status,
    );
  }

  const expectedLength = end - start + 1;
  const contentRange = response.headers.get("Content-Range");
  const match = contentRange?.match(/^bytes (\d+)-(\d+)\/(\d+|\*)$/i);
  if (!match || Number(match[1]) !== start || Number(match[2]) !== end) {
    throw new RangeResponseError("El servidor devolvió un Content-Range incompatible.");
  }
  if (match[3] !== "*" && Number(match[3]) <= end) {
    throw new RangeResponseError("El tamaño total indicado en Content-Range es inválido.");
  }

  const contentLength = response.headers.get("Content-Length");
  if (contentLength !== null && Number(contentLength) !== expectedLength) {
    throw new RangeResponseError("Content-Length no coincide con el rango solicitado.");
  }

  const bytes = new Uint8Array(await response.arrayBuffer());
  if (signal?.aborted) throw abortError(signal);
  if (bytes.byteLength !== expectedLength) {
    throw new RangeResponseError("El servidor entregó un fragmento incompleto.");
  }
  return bytes;
}

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

/** Fetches a bounded byte range. Only transient/network failures are retried. */
export async function fetchRange(
  url: string,
  start: number,
  end: number,
  signal: AbortSignal,
  fetcher: RangeFetcher = fetch,
): Promise<Uint8Array> {
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end < start) {
    throw new RangeError("El rango HTTP solicitado no es válido.");
  }

  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (signal.aborted) throw abortError(signal);
    try {
      const response = await fetcher(url, {
        method: "GET",
        headers: { Range: `bytes=${start}-${end}` },
        signal,
        cache: "no-store",
      });
      if (isRetryableStatus(response.status) && attempt < 2) {
        await wait(250 * (2 ** attempt), signal);
        continue;
      }
      return await readRangeResponse(response, start, end, signal);
    } catch (error) {
      if (signal.aborted) throw abortError(signal);
      if (error instanceof RangeResponseError) {
        if (!isRetryableStatus(error.status ?? 0) || attempt >= 2) throw error;
      } else if (attempt >= 2) {
        throw new Error("No se pudo recuperar el fragmento de audio tras varios intentos.", {
          cause: error,
        });
      }
      lastError = error;
      await wait(250 * (2 ** attempt), signal);
    }
  }
  throw new Error("No se pudo recuperar el fragmento de audio.", { cause: lastError });
}
