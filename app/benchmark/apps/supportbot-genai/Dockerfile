FROM node:20-alpine
WORKDIR /srv
COPY package.json ./
RUN npm install --omit=dev
COPY server/dist ./server/dist
COPY config ./config
USER node
CMD ["node", "server/dist/index.js"]
