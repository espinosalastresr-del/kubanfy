import test from "node:test";
import assert from "node:assert/strict";
import { fetchRange, readRangeResponse, RangeResponseError } from "../src/rangeTransport.ts";

function partial(bytes, start = 0, total = 100) {
  return new Response(bytes, {
    status: 206,
    headers: {
      "Content-Range": `bytes ${start}-${start + bytes.length - 1}/${total}`,
      "Content-Length": String(bytes.length),
    },
  });
}

test("accepts an exact partial response", async () => {
  const result = await readRangeResponse(partial(Uint8Array.from([1, 2, 3, 4])), 0, 3);
  assert.deepEqual([...result], [1, 2, 3, 4]);
});

test("rejects a server that ignores Range and returns the whole object", async () => {
  const response = new Response(new Uint8Array(100), { status: 200 });
  await assert.rejects(
    readRangeResponse(response, 0, 3),
    (error) => error instanceof RangeResponseError && /descarga completa/.test(error.message),
  );
});

test("rejects a mismatched Content-Range", async () => {
  const response = partial(Uint8Array.from([1, 2, 3, 4]), 4);
  await assert.rejects(readRangeResponse(response, 0, 3), /Content-Range incompatible/);
});

test("rejects truncated range bodies", async () => {
  const response = new Response(Uint8Array.from([1, 2]), {
    status: 206,
    headers: { "Content-Range": "bytes 0-3/100", "Content-Length": "4" },
  });
  await assert.rejects(readRangeResponse(response, 0, 3), /fragmento incompleto/);
});

test("retries transient HTTP failures and then returns the exact range", async () => {
  const controller = new AbortController();
  let calls = 0;
  const result = await fetchRange(
    "https://media.example/track.kby2",
    8,
    11,
    controller.signal,
    async () => {
      calls += 1;
      if (calls === 1) return new Response(null, { status: 503 });
      return partial(Uint8Array.from([8, 9, 10, 11]), 8);
    },
  );
  assert.equal(calls, 2);
  assert.deepEqual([...result], [8, 9, 10, 11]);
});

test("does not retry malformed range responses", async () => {
  const controller = new AbortController();
  let calls = 0;
  await assert.rejects(
    fetchRange("https://media.example/track.kby2", 0, 3, controller.signal, async () => {
      calls += 1;
      return new Response(new Uint8Array(4), { status: 200 });
    }),
    RangeResponseError,
  );
  assert.equal(calls, 1);
});

test("aborts without retrying", async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  await assert.rejects(
    fetchRange("https://media.example/track.kby2", 0, 3, controller.signal, async () => {
      calls += 1;
      return partial(Uint8Array.from([0, 1, 2, 3]));
    }),
    { name: "AbortError" },
  );
  assert.equal(calls, 0);
});
