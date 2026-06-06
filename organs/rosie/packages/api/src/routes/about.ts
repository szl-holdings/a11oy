/**
 * @file packages/api/src/routes/about.ts
 * @description GET /v1/about — about-rosie metadata. Backs the Gradio "About" tab.
 */

import { Hono } from 'hono';
import type { AppEnv } from '../lib/env.ts';
import type { About } from '../types/index.ts';

export const aboutRoute = new Hono<AppEnv>();

aboutRoute.get('/', (c) => {
  const svc = c.get('services');
  const body: About = {
    name: 'rosie-api',
    version: svc.version,
    surfaces: ['rosie-widget', 'rosie-operator-console'],
    doctrine_version: 'v7',
    repository: 'https://github.com/szl-holdings/rosie',
  };
  return c.json(body);
});
