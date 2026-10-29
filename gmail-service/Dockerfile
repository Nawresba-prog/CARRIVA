FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY server.js lib.js ./
USER node
CMD ["node", "server.js"]
