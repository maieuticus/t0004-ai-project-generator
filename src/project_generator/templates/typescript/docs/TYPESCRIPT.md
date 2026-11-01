# TypeScript starter

Requires Node.js 24 and npm. From the `typescript/` directory:

```text
npm ci --ignore-scripts
npm run build
npm test
npm run start
```

The `package-lock.json` pins the development dependencies. The example uses
TypeScript with strict checking and NodeNext module resolution. Tests use the
Node.js test runner. `node_modules/` and `dist/` are local build outputs.

The generator does not install npm packages during planning or apply. Once the
TypeScript module is publicly available, the project check will run `verify`
after dependencies have been installed explicitly or by CI.
