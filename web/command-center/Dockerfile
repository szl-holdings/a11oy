# Not a Space image. Do not deploy this folder to Hugging Face.
# Inv6 forbids COPY . . hologram runtimes. Explicit paths only.
# Local run remains: npm install && npm run dev
FROM node:22-alpine
WORKDIR /app
COPY package.json ./
COPY tsconfig.json ./
COPY vite.config.ts ./
COPY index.html ./
COPY public ./public
COPY src ./src
RUN npm install && npm run build
EXPOSE 4173
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "4173"]
