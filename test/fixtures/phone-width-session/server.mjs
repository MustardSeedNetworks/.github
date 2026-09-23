#!/usr/bin/env node
// A stand-in for a product daemon: HTTPS on a self-signed certificate, and every
// route answers with the sign-in screen until the browser carries a session.
// That is the shape seed, stem and niac-go present to the phone-width gate, and
// the reason a static serve cannot check them.
//
// usage: TLS_DIR=<dir from make-cert.sh> PORT=<n> node server.mjs

import { readFileSync } from 'node:fs'
import { createServer } from 'node:https'
import { dirname, join } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const pages = join(dirname(fileURLToPath(import.meta.url)), '..', 'phone-width')
const tls = process.env.TLS_DIR
const port = Number(process.env.PORT)
if (!tls || !port) {
  process.stderr.write('TLS_DIR and PORT are required\n')
  process.exit(2)
}

const COOKIE = 'fixture-session=signed-in'

const SIGN_IN_PAGE = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Sign in</title>
  </head>
  <body><form><label>Password <input type="password" /></label></form></body>
</html>`

const server = createServer(
  { key: readFileSync(join(tls, 'key.pem')), cert: readFileSync(join(tls, 'cert.pem')) },
  (request, response) => {
    const path = new URL(request.url, 'https://localhost').pathname
    if (request.method === 'POST' && path === '/sign-in') {
      response
        .writeHead(204, { 'set-cookie': `${COOKIE}; Path=/; Secure; HttpOnly; SameSite=Strict` })
        .end()
      return
    }
    if (path === '/_shell.css') {
      response.writeHead(200, { 'content-type': 'text/css' }).end(readFileSync(join(pages, '_shell.css')))
      return
    }
    const signedIn = (request.headers.cookie ?? '').split(/;\s*/).includes(COOKIE)
    response
      .writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
      .end(signedIn ? readFileSync(join(pages, 'index.html')) : SIGN_IN_PAGE)
  },
)
server.listen(port, '127.0.0.1')
