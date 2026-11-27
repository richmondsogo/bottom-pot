import fs from "node:fs"
import path from "node:path"
import { fileURLToPath, URL } from "node:url"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig, loadEnv, type Plugin } from "vite"
import {
  PRERENDERED_SUBROUTES,
  buildRobotsTxt,
  buildSitemapXml,
  injectRouteMetadata,
  resolveSiteOrigin,
} from "./src/lib/routeMetadata.ts"

export function routeMetadataPlugin(siteOrigin: string): Plugin {
  return {
    name: "bottom-pot-route-metadata",
    transformIndexHtml(html) {
      return injectRouteMetadata(html, "home", siteOrigin)
    },
    writeBundle(options) {
      const outDir = options.dir
        ? path.resolve(options.dir)
        : fileURLToPath(new URL("./dist", import.meta.url))
      const rootHtmlPath = path.join(outDir, "index.html")
      if (!fs.existsSync(rootHtmlPath)) {
        return
      }
      const rootHtml = fs.readFileSync(rootHtmlPath, "utf-8")

      for (const { slug, route } of PRERENDERED_SUBROUTES) {
        const routeDir = path.join(outDir, slug)
        fs.mkdirSync(routeDir, { recursive: true })
        const routeHtml = injectRouteMetadata(rootHtml, route, siteOrigin)
        fs.writeFileSync(path.join(routeDir, "index.html"), routeHtml, "utf-8")
      }

      fs.writeFileSync(path.join(outDir, "robots.txt"), buildRobotsTxt(siteOrigin), "utf-8")
      fs.writeFileSync(path.join(outDir, "sitemap.xml"), buildSitemapXml(siteOrigin), "utf-8")
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const siteOrigin = resolveSiteOrigin({
    VITE_SITE_URL: env.VITE_SITE_URL || process.env.VITE_SITE_URL,
    VERCEL_PROJECT_PRODUCTION_URL: process.env.VERCEL_PROJECT_PRODUCTION_URL,
  })

  return {
    plugins: [react(), tailwindcss(), routeMetadataPlugin(siteOrigin)],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/search": {
          target: "http://127.0.0.1:8000",
          bypass: (req) => {
            if (req.headers.accept?.includes("text/html")) {
              return "/index.html"
            }
          },
        },
        "/api/admin": "http://127.0.0.1:8000",
        "/api/eligibility": "http://127.0.0.1:8000",
        "/health": "http://127.0.0.1:8000",
        "/subscribe": "http://127.0.0.1:8000",
      },
    },
  }
})
