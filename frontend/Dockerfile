
# Stage 1: Build React application
FROM node:24-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Use relative API paths through Nginx
ENV VITE_API_URL=/api/v1

RUN npm run build


# Stage 2: Nginx production server
FROM nginxinc/nginx-unprivileged:alpine

USER root

RUN rm -rf /usr/share/nginx/html/*

COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]