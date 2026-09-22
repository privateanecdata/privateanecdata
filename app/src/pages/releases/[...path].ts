// Serves the static files of a published release exactly as tools/release.py wrote them.
// Read-only; no listing; nothing outside the releases directory is reachable.
import type { APIRoute } from 'astro';
import { createReadStream } from 'node:fs';
import { Readable } from 'node:stream';
import { releaseFile } from '../../lib/releases';

const TYPES: Record<string, string> = {
  json: 'application/json; charset=utf-8',
  svg: 'image/svg+xml',
  txt: 'text/plain; charset=utf-8',
  md: 'text/markdown; charset=utf-8',
  pem: 'application/x-pem-file',
  sig: 'application/octet-stream',
  ots: 'application/octet-stream',
};

export const GET: APIRoute = ({ params }) => {
  const path = params.path ?? '';
  const ext = path.split('.').pop() ?? '';
  const type = TYPES[ext];
  const f = type ? releaseFile(path) : null;
  if (!f) return new Response('Not found', { status: 404 });
  return new Response(Readable.toWeb(createReadStream(f.full)) as ReadableStream, {
    headers: {
      'Content-Type': type,
      'Content-Length': String(f.size),
      // Releases are immutable once published; a later release never changes an earlier one.
      'Cache-Control': 'public, max-age=86400',
    },
  });
};
