# Two stages. Stage 1 has Node and all build tools; stage 2 is only nginx plus the
# built static files. The final image never contains node_modules (~100MB).

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci = install exactly what package-lock.json says (fails if they disagree).
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
