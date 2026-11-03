import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import pluginQuery from "@tanstack/eslint-plugin-query";
import boundaries from "eslint-plugin-boundaries";

// Module boundaries from docs/ARCHITECTURE.md:
//   app → screens → features → shared, a feature never imports another feature,
//   and features are imported only through their index.ts.
const ENTRY = "index.{ts,tsx}";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  ...pluginQuery.configs["flat/recommended"],
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { boundaries },
    settings: {
      "import/resolver": { typescript: { alwaysTryTypes: true } },
      "boundaries/legacy-templates": false,
      "boundaries/elements": [
        { type: "app", pattern: "src/app" },
        { type: "screen", pattern: "src/screens/*", capture: ["name"] },
        { type: "feature", pattern: "src/features/*", capture: ["name"] },
        { type: "shared", pattern: "src/shared/*", capture: ["name"] },
      ],
    },
    rules: {
      ...boundaries.configs.recommended.rules,
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          policies: [
            {
              from: { element: { type: "app" } },
              allow: {
                to: [
                  { element: { type: "screen", fileInternalPath: ENTRY } },
                  { element: { type: "shared" } },
                ],
              },
            },
            {
              from: { element: { type: "screen" } },
              allow: {
                to: [
                  { element: { type: "feature", fileInternalPath: ENTRY } },
                  { element: { type: "shared" } },
                ],
              },
            },
            {
              from: { element: { type: "feature" } },
              allow: { to: { element: { type: "shared" } } },
            },
            {
              from: { element: { type: "shared" } },
              allow: { to: { element: { type: "shared" } } },
            },
          ],
        },
      ],
    },
  },
  // Dates are only handled through src/shared/utils/date.ts (one place to swap for a date library).
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/shared/utils/date.ts"],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "Date", message: "Use the helpers of @/shared/utils/date instead of Date." },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "MemberExpression[object.name='Intl'][property.name='DateTimeFormat']",
          message: "Format dates with formatDate from @/shared/utils/date.",
        },
        {
          selector: "CallExpression[callee.property.name=/^toLocale(Date|Time)?String$/]",
          message: "Format dates with formatDate from @/shared/utils/date.",
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "playwright-report/**",
    "test-results/**",
    "src/shared/api/schema.gen.ts",
  ]),
]);

export default eslintConfig;
