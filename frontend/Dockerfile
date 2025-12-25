# GrindLab Frontend Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Build stage
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files first for better cache utilization
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --silent

# Copy source code
COPY . .

# Build arguments (can be overridden at build time)
ARG VITE_API_BASE_URL=http://127.0.0.1:8000

# Build the application with API URL
RUN VITE_API_BASE_URL=${VITE_API_BASE_URL} npm run build

# Stage 2: Production stage with nginx
FROM nginx:alpine as production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Default command (nginx runs in foreground)
CMD ["nginx", "-g", "daemon off;"]
