# --- build stage ---
  FROM node:20-alpine AS builder
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  # Vite will automatically pick up .env.production
  RUN npm run build
  
  # --- runtime stage ---
  FROM nginx:1.27-alpine
  # наш Nginx listens on 8080 (Cloud Run will give $PORT=8080)
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  # static files in nginx default folder
  COPY --from=builder /app/dist /usr/share/nginx/html
  EXPOSE 8080
  CMD ["nginx", "-g", "daemon off;"]
  