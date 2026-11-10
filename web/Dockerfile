# Stage 1: Build Frontend Assets
FROM node:20-alpine AS builder

WORKDIR /app

# Avoid downloading heavy Electron desktop binaries inside container build
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1

# Install dependencies using package-lock.json
COPY package*.json ./
RUN npm ci

# Copy frontend source code and public assets
COPY . .

# Build production bundle with Vite
RUN npm run build

# Stage 2: Serve via Nginx
FROM nginx:alpine

# Clean default Nginx files
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:80/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]

