# Etapa 1: compilación de la aplicación React (Vite)
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_URL=/api
ARG VITE_APP_NAME=SIPD-UDES
ARG VITE_INSTITUTION_NAME="Universidad de Santander"
ENV VITE_API_URL=$VITE_API_URL VITE_APP_NAME=$VITE_APP_NAME VITE_INSTITUTION_NAME=$VITE_INSTITUTION_NAME
RUN npm run build

# Etapa 2: Nginx sirve los estáticos y hace proxy de /api al backend
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
