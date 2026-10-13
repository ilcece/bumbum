/** Never log exception messages, SQL, request bodies, hashes or credentials. */
export function safeErrorDetails(error: unknown) {
  const e = error && typeof error === 'object' ? error as Record<string, unknown> : {};
  const types = new Set(['Error','TypeError','RangeError','ReferenceError','SyntaxError','URIError']);
  const errorType = typeof e.name === 'string' && types.has(e.name) ? e.name : 'Error';
  const errorCode = typeof e.code === 'string' && /^[A-Z][A-Z0-9_]{0,63}$/.test(e.code) ? e.code : undefined;
  // Only actual stack frame lines and known application source filenames.
  const sites = typeof e.stack === 'string' ? e.stack.split('\n').filter(line => /^\s*at\s/.test(line)).flatMap(line => {
    const match = line.match(/(?:\/app\/dist|\/workspace\/bumbum\/src)\/(app|db|security|server|cli|diagnostics)\.(?:js|ts):(\d{1,8}):(\d{1,8})(?:\)|$)/);
    return match ? [`${match[1]}:${match[2]}:${match[3]}`] : [];
  }).slice(0,6) : [];
  return { errorType, ...(errorCode ? { errorCode } : {}), sites };
}
