# Next.js dashboard. NEXT_PUBLIC_API_URL is inlined at build time.
#   docker build --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t ccauditor-web app/web
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Run from the build stage: next.config.ts and its loaders are resolved at `next start` too.
FROM build
ENV NODE_ENV=production PORT=3000
RUN chown -R node:node /app/.next
USER node
EXPOSE 3000
CMD ["npm", "start"]
