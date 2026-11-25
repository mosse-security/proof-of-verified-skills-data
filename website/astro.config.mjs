import { defineConfig } from 'astro/config';
import { siteUrl } from './site-config.mjs';

export default defineConfig({
  output: 'static',
  site: siteUrl,
  base: '/',
});
