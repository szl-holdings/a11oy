# Replica-only Command Center surface.
# Does NOT replace SZLHOLDINGS/a11oy (Python runtime) or a-11-oy.com DNS.
FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 7860
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "7860"]
